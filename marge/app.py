"""
An auto-merger of merge requests for GitLab
"""

import contextlib
import logging
import re
import sys
import tempfile
from datetime import timedelta

import configargparse

from . import bot
from . import interval
from . import gitlab
from . import user as user_module


class MargeBotCliArgError(Exception):
    pass


def time_interval(str_interval):
    try:
        quant, unit = re.match(r'\A([\d.]+) ?(h|m(?:in)?|s)?\Z', str_interval).groups()
        translate = {'h': 'hours', 'm': 'minutes', 'min': 'minutes', 's': 'seconds'}
        return timedelta(**{translate[unit or 's']: float(quant)})
    except (AttributeError, ValueError) as err:
        raise configargparse.ArgumentTypeError(
                'Invalid time interval (e.g. 12[s|min|h]): %s' % str_interval
        ) from err


def _parse_config(args):

    def regexp(str_regex):
        try:
            return re.compile(str_regex)
        except re.error as err:
            raise configargparse.ArgumentTypeError('Invalid regexp: %r (%s)' % (str_regex, err.msg))

    parser = configargparse.ArgParser(
        auto_env_var_prefix='MARGE_',
        ignore_unknown_config_file_keys=True,  # Don't parse unknown args
        config_file_parser_class=configargparse.YAMLConfigFileParser,
        formatter_class=configargparse.ArgumentDefaultsRawHelpFormatter,
        description=__doc__,
    )
    parser.add_argument(
        '--config-file',
        env_var='MARGE_CONFIG_FILE',
        type=str,
        is_config_file=True,
        help='config file path',
    )
    auth_token_group = parser.add_mutually_exclusive_group(required=True)
    auth_token_group.add_argument(
        '--auth-token',
        type=str,
        metavar='TOKEN',
        help=(
            'Your GitLab token.\n'
            'DISABLED because passing credentials on the command line is insecure:\n'
            'You can still set it via ENV variable or config file, or use "--auth-token-file" flag.\n'
        ),
    )
    auth_token_group.add_argument(
        '--auth-token-file',
        type=configargparse.FileType('rt'),
        metavar='FILE',
        help='Path to your GitLab token file.\n',
    )
    parser.add_argument(
        '--gitlab-url',
        type=str,
        required=True,
        metavar='URL',
        help='Your GitLab instance, e.g. "https://gitlab.example.com".\n',
    )
    repo_access = parser.add_mutually_exclusive_group(required=True)
    repo_access.add_argument(
        '--use-https',
        env_var='MARGE_USE_HTTPS',
        action='store_true',
        help='use HTTP(S) instead of SSH for GIT repository access\n',
    )
    repo_access.add_argument(
        '--ssh-key',
        type=str,
        metavar='KEY',
        help=(
            'The private ssh key for marge so it can clone/push.\n'
            'DISABLED because passing credentials on the command line is insecure:\n'
            'You can still set it via ENV variable or config file, or use "--ssh-key-file" flag.\n'
        ),
    )
    repo_access.add_argument(
        '--ssh-key-file',
        type=str,  # because we want a file location, not the content
        metavar='FILE',
        help='Path to the private ssh key for marge so it can clone/push.\n',
    )
    parser.add_argument(
        '--embargo',
        type=interval.IntervalUnion.from_human,
        metavar='INTERVAL[,..]',
        help='Time(s) during which no merging is to take place, e.g. "Friday 1pm - Monday 9am".\n',
    )
    experimental_group = parser.add_mutually_exclusive_group(required=False)
    experimental_group.add_argument(
        '--use-merge-strategy',
        action='store_true',
        help=(
            'Use git merge instead of git rebase to update the *source* branch (EXPERIMENTAL)\n'
            'If you need to use a strict no-rebase workflow (in most cases\n'
            'you don\'t want this, even if you configured gitlab to use merge requests\n'
            'to use merge commits on the *target* branch (the default).)\n'
        ),
    )
    parser.add_argument(
        '--rebase-remotely',
        action='store_true',
        help=(
            "Instead of rebasing in a local clone of the repository, use GitLab's\n"
            "built-in rebase functionality, via their API. Note that Marge can't add\n"
            "information in the commits in this case.\n"
        ),
    )
    parser.add_argument(
        '--add-tested',
        action='store_true',
        help='Add "Tested: marge-bot <$MR_URL>" for the final commit on branch after it passed CI.\n',
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Enable processing MRs in batches\n',
    )
    parser.add_argument(
        '--add-part-of',
        action='store_true',
        help='Add "Part-of: <$MR_URL>" to each commit in MR.\n',
    )
    parser.add_argument(
        '--add-reviewers',
        action='store_true',
        help='Add "Reviewed-by: $approver" for each approver of MR to each commit in MR.\n',
    )
    parser.add_argument(
        '--impersonate-approvers',
        action='store_true',
        help='Marge-bot pushes effectively don\'t change approval status.\n',
    )
    parser.add_argument(
        '--merge-order',
        default='created_at',
        choices=('created_at', 'updated_at', 'assigned_at'),
        help='Order marge merges assigned requests. created_at (default), updated_at or assigned_at.\n',
    )
    parser.add_argument(
        '--approval-reset-timeout',
        type=time_interval,
        default='0s',
        help=(
            'How long to wait for approvals to reset after pushing.\n'
            'Only useful with the "new commits remove all approvals" option in a project\'s settings.\n'
            'This is to handle the potential race condition where approvals don\'t reset in GitLab\n'
            'after a force push due to slow processing of the event.\n'
        ),
    )
    parser.add_argument(
        '--project-regexp',
        type=regexp,
        default='.*',
        help="Only process projects that match; e.g. 'some_group/.*' or '(?!exclude/me)'.\n",
    )
    parser.add_argument(
        '--ci-timeout',
        type=time_interval,
        default='15min',
        help='How long to wait for CI to pass.\n',
    )
    parser.add_argument(
        '--max-ci-time-in-minutes',
        type=int,
        default=None,
        help='Deprecated; use --ci-timeout.\n',
    )
    parser.add_argument(
        '--git-timeout',
        type=time_interval,
        default='120s',
        help='How long a single git operation can take.\n'
    )
    parser.add_argument(
        '--git-reference-repo',
        type=str,
        default=None,
        help='A reference repo to be used when git cloning.\n'
    )
    parser.add_argument(
        '--branch-regexp',
        type=regexp,
        default='.*',
        help='Only process MRs whose target branches match the given regular expression.\n',
    )
    parser.add_argument(
        '--source-branch-regexp',
        type=regexp,
        default='.*',
        help='Only process MRs whose source branches match the given regular expression.\n',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Debug logging (includes all HTTP requests etc).\n',
    )
    parser.add_argument(
        '--use-no-ff-batches',
        action='store_true',
        help='Disable fast forwarding when merging MR batches'
    )
    parser.add_argument(
        '--use-merge-commit-batches',
        action='store_true',
        help='Use merge commit when creating batches, so that the commits in the batch MR '
             'will be the same with in individual MRs. Requires sudo scope in the access token.\n',
    )
    parser.add_argument(
        '--skip-ci-batches',
        action='store_true',
        help='Skip CI when updating individual MRs when using batches'
    )
    parser.add_argument(
        '--cli',
        action='store_true',
        help='Run marge-bot as a single CLI command, not a service'
    )
    config = parser.parse_args(args)

    if config.use_merge_strategy and config.batch:
        raise MargeBotCliArgError('--use-merge-strategy and --batch are currently mutually exclusive')
    if config.use_merge_strategy and config.add_tested:
        raise MargeBotCliArgError('--use-merge-strategy and --add-tested are currently mutually exclusive')
    if config.rebase_remotely:
        conflicting_flag = [
            '--use-merge-strategy',
            '--add-tested',
            '--add-reviewers',
            '--add-part-of',
        ]
        for flag in conflicting_flag:
            if getattr(config, flag[2:].replace("-", "_")):
                raise MargeBotCliArgError('--rebase-remotely and %s are mutually exclusive' % flag)

    cli_args = []
    # pylint: disable=protected-access
    for _, (_, value) in parser._source_to_settings.get(configargparse._COMMAND_LINE_SOURCE_KEY, {}).items():
        cli_args.extend(value)
    for bad_arg in ['--auth-token', '--ssh-key']:
        if any(bad_arg in arg for arg in cli_args):
            raise MargeBotCliArgError('"%s" can only be set via ENV var or config file.' % bad_arg)
    return config


@contextlib.contextmanager
def _secret_auth_token_and_ssh_key(options):
    auth_token = options.auth_token or options.auth_token_file.readline().strip()
    if options.use_https:
        yield auth_token, None
    elif options.ssh_key_file:
        yield auth_token, options.ssh_key_file
    else:
        with tempfile.NamedTemporaryFile(mode='w', prefix='ssh-key-') as tmp_ssh_key_file:
            try:
                tmp_ssh_key_file.write(options.ssh_key + '\n')
                tmp_ssh_key_file.flush()
                yield auth_token, tmp_ssh_key_file.name
            finally:
                tmp_ssh_key_file.close()


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    logging.basicConfig()

    options = _parse_config(args)

    if options.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger("requests").setLevel(logging.WARNING)

    with _secret_auth_token_and_ssh_key(options) as (auth_token, ssh_key_file):
        api = gitlab.Api(options.gitlab_url, auth_token)
        user = user_module.User.myself(api)
        if options.max_ci_time_in_minutes:
            logging.warning(
                "--max-ci-time-in-minutes is DEPRECATED, use --ci-timeout %dmin",
                options.max_ci_time_in_minutes
            )
            options.ci_timeout = timedelta(minutes=options.max_ci_time_in_minutes)

        if options.batch:
            logging.warning('Experimental batch mode enabled')

        if options.use_merge_strategy:
            fusion = bot.Fusion.merge
        elif options.rebase_remotely:
            version = api.version()
            if version.release < (11, 6):
                raise Exception(
                    "Need GitLab 11.6+ to use rebase through the API, "
                    "but your instance is {}".format(version)
                )
            fusion = bot.Fusion.gitlab_rebase
        else:
            fusion = bot.Fusion.rebase

        config = bot.BotConfig(
            user=user,
            use_https=options.use_https,
            auth_token=auth_token,
            ssh_key_file=ssh_key_file,
            project_regexp=options.project_regexp,
            git_timeout=options.git_timeout,
            git_reference_repo=options.git_reference_repo,
            branch_regexp=options.branch_regexp,
            source_branch_regexp=options.source_branch_regexp,
            merge_order=options.merge_order,
            merge_opts=bot.MergeJobOptions.default(
                add_tested=options.add_tested,
                add_part_of=options.add_part_of,
                add_reviewers=options.add_reviewers,
                reapprove=options.impersonate_approvers,
                approval_timeout=options.approval_reset_timeout,
                embargo=options.embargo,
                ci_timeout=options.ci_timeout,
                fusion=fusion,
                use_no_ff_batches=options.use_no_ff_batches,
                use_merge_commit_batches=options.use_merge_commit_batches,
                skip_ci_batches=options.skip_ci_batches,
            ),
            batch=options.batch,
            cli=options.cli,
        )

        marge_bot = bot.Bot(api=api, config=config)
        marge_bot.start()
