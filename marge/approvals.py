import logging as log
import fnmatch
import re
import shlex

from . import gitlab

GET, POST, PUT = gitlab.GET, gitlab.POST, gitlab.PUT


class Approvals(gitlab.Resource):
    """Approval info for a MergeRequest."""

    def refetch_info(self):
        gitlab_version = self._api.version()

        if gitlab_version.is_ee:
            self._info = self._api.call(GET(self.get_approvals_url(self)))
        else:
            self._info = self.get_approvers_ce()

    def get_approvers_ce(self):
        """get approvers status using thumbs on merge request
        """
        gitlab_version = self._api.version()

        # Gitlab supports approvals in free version after 13.2.0
        approval_api_results = dict(approved_by=[])
        if gitlab_version.release >= (13, 2, 0):
            approval_api_results = self._api.call(GET(self.get_approvals_url(self)))

        owner_file = self.get_codeowners_ce()
        if not owner_file['owners']:
            log.info("No CODEOWNERS file in master, continuing without approvers flow")
            return dict(self._info, approvals_left=0, approved_by=[], codeowners=[])

        code_owners = self.determine_responsible_owners(owner_file['owners'], self.get_changes_ce())

        if not code_owners:
            log.info("No matched code owners, continuing without approvers flow")
            return dict(self._info, approvals_left=0, approved_by=[], codeowners=[])

        awards = self.get_awards_ce()

        up_votes = [e for e in awards if e['name'] == 'thumbsup' and e['user']['username'] in code_owners]
        for approver in approval_api_results['approved_by']:
            if approver['user']['username'] in code_owners \
                    and not any(ex['user']['username'] == approver['user']['username'] for ex in up_votes):
                up_votes.append(approver)

        approvals_required = len(code_owners)

        if owner_file['approvals_required'] > 0:
            approvals_required = owner_file['approvals_required']

        approvals_left = max(approvals_required - len(up_votes), 0)

        return dict(self._info, approvals_left=approvals_left, approved_by=up_votes, codeowners=code_owners)

    def determine_responsible_owners(self, owners_glob, changes):
        owners = set([])

        # Always add global users
        if '*' in owners_glob:
            owners.update(owners_glob['*'])

        if 'changes' not in changes:
            log.info("No changes in merge request!?")
            return owners

        for change in changes['changes']:
            for glob, users in owners_glob.items():
                test_glob = glob
                if glob.endswith('/'):
                    test_glob += "*"

                if 'new_path' in change and fnmatch.fnmatch(change['new_path'], test_glob):
                    owners.update(users)

        return owners

    def get_changes_ce(self):
        changes_url = '/projects/{0.project_id}/merge_requests/{0.iid}/changes'
        changes_url = changes_url.format(self)

        return self._api.call(GET(changes_url))

    def get_awards_ce(self):
        emoji_url = '/projects/{0.project_id}/merge_requests/{0.iid}/award_emoji'
        emoji_url = emoji_url.format(self)
        return self._api.call(GET(emoji_url))

    def get_codeowners_ce(self):
        config_file = self._api.repo_file_get(self.project_id, "CODEOWNERS", "master")
        owner_globs = {}
        required = 0
        required_regex = re.compile('.*MARGEBOT_MINIMUM_APPROVERS *= *([0-9]+)')

        if config_file is None:
            return {"approvals_required": 0, "owners": {}}

        for line in config_file['content'].splitlines():
            if 'MARGEBOT_' in line:
                match = required_regex.match(line)
                if match:
                    required = int(match.group(1))

            if line != "" and not line.startswith(' ') and not line.startswith('#'):
                elements = shlex.split(line)
                glob = elements.pop(0)
                owner_globs.setdefault(glob, set([]))

                for user in elements:
                    owner_globs[glob].add(user.strip('@'))

        return {"approvals_required": required, "owners": owner_globs}

    @property
    def approvers_string(self):
        reviewer_string = ""

        if len(self.codeowners) == 1:
            reviewer_string = '@' + self.codeowners.pop()
        elif len(self.codeowners) > 1:
            reviewer_ats = ["@" + reviewer for reviewer in self.codeowners]
            reviewer_string = '{} or {}'.format(', '.join(reviewer_ats[:-1]), reviewer_ats[-1])

        return reviewer_string

    def get_approvals_url(self, obj):
        gitlab_version = self._api.version()

        if gitlab_version.release >= (9, 2, 2):
            return '/projects/{0.project_id}/merge_requests/{0.iid}/approvals'.format(obj)

        # GitLab botched the v4 api before 9.2.3
        return '/projects/{0.project_id}/merge_requests/{0.id}/approvals'.format(obj)

    @property
    def iid(self):
        return self.info['iid']

    @property
    def project_id(self):
        return self.info['project_id']

    @property
    def approvals_left(self):
        return self.info['approvals_left'] or 0

    @property
    def sufficient(self):
        return not self.info['approvals_left']

    @property
    def approver_usernames(self):
        return [who['user']['username'] for who in self.info['approved_by']]

    @property
    def approver_ids(self):
        """Return the uids of the approvers."""
        return [who['user']['id'] for who in self.info['approved_by']]

    @property
    def codeowners(self):
        """Only used for gitlab CE"""
        if 'codeowners' in self.info:
            return self.info['codeowners']

        return {}

    def reapprove(self):
        """Impersonates the approvers and re-approves the merge_request as them.

        The idea is that we want to get the approvers, push the rebased branch
        (which may invalidate approvals, depending on GitLab settings) and then
        restore the approval status.
        """
        self.approve(self)

    def approve(self, obj):
        """Approve an object which can be a merge_request or an approval."""
        gitlab_version = self._api.version()

        # Gitlab supports approvals in free version after 13.2.0
        if gitlab_version.is_ee or gitlab_version.release >= (13, 2, 0):
            for uid in self.approver_ids:
                self._api.call(POST(self.get_approvals_url(obj)), sudo=uid)
