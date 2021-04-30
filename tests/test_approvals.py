from unittest.mock import call, Mock, patch

import pytest

from marge.gitlab import Api, GET, POST, Version
from marge.approvals import Approvals
from marge.merge_request import MergeRequest
import marge.user
# testing this here is more convenient
from marge.job import CannotMerge, _get_reviewer_names_and_emails

CODEOWNERS = {
    "content": """
# MARGEBOT_MINIMUM_APPROVERS = 2
# This is an example code owners file, lines starting with a `#` will
# be ignored.

* @default-codeowner @test-user1
* @test-user1 @ebert

unmatched/* @test5
"""
}

# pylint: disable=anomalous-backslash-in-string
CODEOWNERS_FULL = {
    "content": """
# MARGEBOT_MINIMUM_APPROVERS=3
# This is an example code owners file, lines starting with a `#` will
# be ignored.

# app/ @commented-rule

# We can specify a default match using wildcards:
* @default-codeowner

# Rules defined later in the file take precedence over the rules
# defined before.
# This will match all files for which the file name ends in `.rb`
*.rb @ruby-owner

# Files with a `#` can still be accesssed by escaping the pound sign
\#file_with_pound.rb @owner-file-with-pound

# Multiple codeowners can be specified, separated by spaces or tabs
CODEOWNERS @multiple @code @owners

# Both usernames or email addresses can be used to match
# users. Everything else will be ignored. For example this will
# specify `@legal` and a user with email `janedoe@gitlab.com` as the
# owner for the LICENSE file
LICENSE @legal this_does_not_match janedoe@gitlab.com

# Ending a path in a `/` will specify the code owners for every file
# nested in that directory, on any level
/docs/ @all-docs

# Ending a path in `/*` will specify code owners for every file in
# that directory, but not nested deeper. This will match
# `docs/index.md` but not `docs/projects/index.md`
/docs/* @root-docs

# This will make a `lib` directory nested anywhere in the repository
# match
lib/ @lib-owner

# This will only match a `config` directory in the root of the
# repository
/config/ @config-owner

# If the path contains spaces, these need to be escaped like this:
path\ with\ spaces/ @space-owner
"""  # noqa: W605
}

AWARDS = [
    {
        "id": 1,
        "name": "thumbsdown",
        "user": {
            "name": "Test User 1",
            "username": "test-user1",
            "id": 3,
            "state": "active",
        },
        "created_at": "2020-04-24T13:16:23.614Z",
        "updated_at": "2020-04-24T13:16:23.614Z",
        "awardable_id": 11,
        "awardable_type": "MergeRequest"
    },
    {
        "id": 2,
        "name": "thumbsup",
        "user": {
            "name": "Roger Ebert",
            "username": "ebert",
            "id": 2,
            "state": "active",
        },
        "created_at": "2020-04-24T13:16:23.614Z",
        "updated_at": "2020-04-24T13:16:23.614Z",
        "awardable_id": 12,
        "awardable_type": "MergeRequest"
    }
]

CHANGES = {
    "changes": [
        {
            "old_path": "README",
            "new_path": "README",
            "a_mode": "100644",
            "b_mode": "100644",
            "new_file": False,
            "renamed_file": False,
            "deleted_file": False,
            "diff": "",
        },
        {
            "old_path": "main.go",
            "new_path": "main.go",
            "a_mode": "100644",
            "b_mode": "100644",
            "new_file": False,
            "renamed_file": False,
            "deleted_file": False,
            "diff": ""
        }
    ]
}


INFO = {
    "id": 5,
    "iid": 6,
    "project_id": 1,
    "title": "Approvals API",
    "description": "Test",
    "state": "opened",
    "created_at": "2016-06-08T00:19:52.638Z",
    "updated_at": "2016-06-08T21:20:42.470Z",
    "merge_status": "can_be_merged",
    "approvals_required": 3,
    "approvals_left": 1,
    "approved_by": [
        {
            "user": {
                "name": "Administrator",
                "username": "root",
                "id": 1,
                "state": "active",
                "avatar_url": "".join([
                    "http://www.gravatar.com/avatar/",
                    "e64c7d89f26bd1972efa854d13d7dd61?s=80\u0026d=identicon",
                ]),
                "web_url": "http://localhost:3000/u/root"
            },
        },
        {
            "user": {
                "name": "Roger Ebert",
                "username": "ebert",
                "id": 2,
                "state": "active",
            }
        }
    ]
}
USERS = {
    1: {
        "name": "Administrator",
        "username": "root",
        "id": 1,
        "state": "active",
        "email": "root@localhost",
    },
    2: {
        "name": "Roger Ebert",
        "username": "ebert",
        "id": 2,
        "state": "active",
        "email": "ebert@example.com",
    },
}


# pylint: disable=attribute-defined-outside-init
class TestApprovals:

    def setup_method(self, _method):
        self.api = Mock(Api)
        self.api.version = Mock(return_value=Version.parse('9.2.3-ee'))
        self.approvals = Approvals(api=self.api, info=INFO)

    def test_fetch_from_merge_request(self):
        api = self.api
        api.call = Mock(return_value=INFO)

        merge_request = MergeRequest(api, {'id': 74, 'iid': 6, 'project_id': 1234})
        approvals = merge_request.fetch_approvals()

        api.call.assert_called_once_with(GET(
            '/projects/1234/merge_requests/6/approvals'
        ))
        assert approvals.info == INFO

    @patch('marge.approvals.Approvals.get_awards_ce', Mock(return_value=AWARDS))
    @patch('marge.approvals.Approvals.get_changes_ce', Mock(return_value=CHANGES))
    def test_fetch_from_merge_request_ce_compat(self):
        api = self.api
        api.version = Mock(return_value=Version.parse('9.2.3'))
        api.call = Mock()
        api.repo_file_get = Mock(return_value=CODEOWNERS)

        merge_request = MergeRequest(api, {'id': 74, 'iid': 6, 'project_id': 1234})
        approvals = merge_request.fetch_approvals()

        api.call.assert_not_called()
        assert approvals.info == {
            'id': 74,
            'iid': 6,
            'project_id': 1234,
            'approvals_left': 1,
            'approved_by': [AWARDS[1]],
            'codeowners': {'default-codeowner', 'ebert', 'test-user1'},
        }

    def test_properties(self):
        assert self.approvals.project_id == 1
        assert self.approvals.approvals_left == 1
        assert self.approvals.approver_usernames == ['root', 'ebert']
        assert not self.approvals.sufficient

    def test_sufficiency(self):
        good_approvals = Approvals(api=self.api, info=dict(INFO, approvals_required=1, approvals_left=0))
        assert good_approvals.sufficient

    def test_reapprove(self):
        self.approvals.reapprove()
        self.api.call.has_calls([
            call(POST(endpoint='/projects/1/merge_requests/6/approve', args={}, extract=None), sudo=1),
            call(POST(endpoint='/projects/1/merge_requests/6/approve', args={}, extract=None), sudo=2)
        ])

    @patch('marge.user.User.fetch_by_id')
    def test_get_reviewer_names_and_emails(self, user_fetch_by_id):
        user_fetch_by_id.side_effect = lambda id, _: marge.user.User(self.api, USERS[id])
        assert _get_reviewer_names_and_emails(commits=[], approvals=self.approvals, api=self.api) == [
            'Administrator <root@localhost>',
            'Roger Ebert <ebert@example.com>'
        ]

    @patch('marge.user.User.fetch_by_id')
    def test_approvals_fails_when_same_author(self, user_fetch_by_id):
        info = dict(INFO, approved_by=list(INFO['approved_by']))
        del info['approved_by'][1]
        approvals = Approvals(self.api, info)
        user_fetch_by_id.side_effect = lambda id, _: marge.user.User(self.api, USERS[id])
        commits = [{'author_email': 'root@localhost'}]
        with pytest.raises(CannotMerge):
            _get_reviewer_names_and_emails(commits=commits, approvals=approvals, api=self.api)

    @patch('marge.user.User.fetch_by_id')
    def test_approvals_succeeds_with_independent_author(self, user_fetch_by_id):
        user_fetch_by_id.side_effect = lambda id, _: marge.user.User(self.api, USERS[id])
        print(INFO['approved_by'])
        commits = [{'author_email': 'root@localhost'}]
        assert _get_reviewer_names_and_emails(commits=commits, approvals=self.approvals, api=self.api) == [
            'Administrator <root@localhost>',
            'Roger Ebert <ebert@example.com>',
        ]

    def test_approvals_ce_get_codeowners_full(self):
        api = self.api
        api.version = Mock(return_value=Version.parse('9.2.3'))
        api.repo_file_get = Mock(return_value=CODEOWNERS_FULL)

        approvals = Approvals(api, {'id': 74, 'iid': 6, 'project_id': 1234})

        assert approvals.get_codeowners_ce() == {
            'approvals_required': 3,
            'owners': {
                '#file_with_pound.rb': {'owner-file-with-pound'},
                '*': {'default-codeowner'},
                '*.rb': {'ruby-owner'},
                '/config/': {'config-owner'},
                '/docs/': {'all-docs'},
                '/docs/*': {'root-docs'},
                'CODEOWNERS': {'owners', 'multiple', 'code'},
                'LICENSE': {'this_does_not_match', 'janedoe@gitlab.com', 'legal'},
                'lib/': {'lib-owner'},
                'path with spaces/': {'space-owner'}
            }
        }

    def test_approvals_ce_get_codeowners_wildcard(self):
        api = self.api
        api.version = Mock(return_value=Version.parse('9.2.3'))
        api.repo_file_get = Mock(return_value=CODEOWNERS)

        approvals = Approvals(api, {'id': 74, 'iid': 6, 'project_id': 1234})

        assert approvals.get_codeowners_ce() == {
            'approvals_required': 2,
            'owners': {'*': {'default-codeowner', 'test-user1', 'ebert'}, 'unmatched/*': {'test5'}}
        }

    @patch('marge.approvals.Approvals.get_awards_ce', Mock(return_value=AWARDS))
    @patch('marge.approvals.Approvals.get_changes_ce', Mock(return_value=CHANGES))
    def test_approvals_ce(self):
        api = self.api
        api.version = Mock(return_value=Version.parse('9.2.3'))
        api.repo_file_get = Mock(return_value=CODEOWNERS)

        merge_request = MergeRequest(api, {'id': 74, 'iid': 6, 'project_id': 1234})
        approvals = merge_request.fetch_approvals()

        result = approvals.get_approvers_ce()

        assert result['approvals_left'] == 1
        assert len(result['approved_by']) == 1

    def test_approvers_string_one(self):
        approvals = Approvals(self.api, {'codeowners': {'ebert'}})

        assert approvals.approvers_string == '@ebert'

    def test_approvers_string_more(self):
        approvals = Approvals(self.api, {'codeowners': {'ebert', 'test-user1'}})

        assert '@ebert' in approvals.approvers_string
        assert '@test-user1' in approvals.approvers_string

    def test_approvers_string_empty(self):
        approvals = Approvals(self.api, {'codeowners': {}})

        assert approvals.approvers_string == ''
