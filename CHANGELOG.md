  * 0.9.5:
    - Feature: Add new choice `assigned_at` to option `merge_order` #268
    - Fix: Wait for merge status to resolve #265
  * 0.9.4:
    - Fix: handle `CannotMerge` which could be raised from `update_merge_request` #275
    - Fix: maintain `batch_mr_sha` value when batch merging with fast forward commits #276
  * 0.9.3:
    - Feature: allow merge commits in batch MRs, to make the commits be exactly the same in
      the sub MRs and the batch MR. Add `--use-merge-commit-batches` and `--skip-ci-batches` options #264
    - Feature: add `--use-no-ff-batches` to disable fast forwarding of batch merges (#256, #259)
  * 0.9.2:
    - Fix: ensure parameters are correct when merging with/without pipelines enabled #251
    - Fix: only delete source branch if forced #193
    - Fix: fix sandboxed build #250
  * 0.9.1:
    - Feature: support passing a timezone with the embargo #228
    - Fix: fix not checking the target project for MRs from forked projects #218
  * 0.9.0:
    - Feature: support rebasing through GitLab's API #160
    - Feature: allow restrict source branches #206
    - Fix: only fetch projects with min access level #166
    - Fix: bump all dependencies (getting rid of vulnerable packages) #179
    - Fix: support multiple assignees #186, #192
    - Fix: fetch pipelines by merge request instead of branch #212
    - Fix: fix unassign when author is Marge #211
    - Enhancement: ignore archived projects #177
    - Enhancement: add a timeout to all gitlab requests #200
    - Enhancement: smaller docker image size  #199
  * 0.8.1
    - Feature: allow merging in order of last-update time #149
  * 0.8.0
    - Feature: allow reference repository in git clone #129
    - Feature: add new stable/master tags for docker images #142
    - Fix: fix TypeError when fetching source project #122
    - Fix: handle CI status 'skipped' #127
    - Fix: handle merging when source branch is master #127
    - Fix: handle error on pushing to protected branches #127
    - Enhancement: add appropriate error if unresolved discussions on merge request #136
    - Enhancement: ensure reviewer and commit author aren't the same #137
  * 0.7.0:
    - Feature: add `--batch` to better support repos with many daily MRs and slow-ish CI (#84, #116)
    - Fix: fix fuse() call when using experimental --use-merge-strategy to update source branch #102
    - Fix: Get latest CI status of a commit filtered by branch #96 (thanks to benjamb)
    - Enhancement: Check MR is mergeable before accepting MR #117 
  * 0.6.1:
    - Fix when target SHA is retrieved #92.
    - Replace word "gitlab" with "GitLab" #93.
  * 0.6.0:
    - Fix issue due to a `master` branch being assumed when removing
      local branches #88.
    - Better error reporting when there are no changes left
      after rebasing #87.
    - Add --approval-reset-timeout option #85.
    - Fix encoding issues under Windows #86.
    - Support new merge-request status "locked" #79.
    - Fixes issue where stale branches in marge's repo could
      lead to conflicts #78.
    - Add experimental --use-merge-strategy flag that uses merge-commits
      instead of rebasing (#72, and also #90 for caveats).
  * 0.5.1:
    - Sleep even less between polling for MRs #75.
  * 0.5.0:
    - Added "default -> config file -> env var -> args" way to configure marge-bot #71
  * 0.4.1:
    - Fixed bug in error handling of commit rewritting (#70 / 1438867)
    - Add --project-regexp argument to restrict to certain target branches $65.
    - Sleep less between merging requests while there are jobs pending #67.
    - Less verborragic logging when --debug is used #66.
  * 0.4.0:
    - The official docker image is now on `smarkets/marge-bot` not (`smarketshq/marge-bot`).
    - Add a --add-part-of option to tag commit messages with originating MR #48.
    - Add a --git-timeout parameter (that takes time units); also add --ci-timeout
      that deprecates --max-ci-time-in-minutes #58.
    - Re-approve immediately after push #53.
    - Always use --ssh-key-file if passed (never ssh-agent or keys from ~/.ssh) #61.
    - Fix bad LOCALE problem in official image (hardcode utf-8 everywhere) #57.
    - Don't blow up on logging bad json responses #51.
    - Grammar fix #52.
  * 0.3.2: Fix support for branches with "/" in their names #50.
  * 0.3.1: Fix start-up error when running as non-admin user #49.
  * 0.3.0:
    - Display better messages when GitLab refuses to merge #32, #33.
    - Handle auto-squash being selected #14.
    - Add `--max-ci-time-in-minutes`, with default of 15 #44.
    - Fix clean-up of `ssh-key-xxx` files #38.
    - All command line args now have an environment var equivalent #35.
  * 0.2.0:
    - Add `--project-regexp` flag, to select which projects to include/exclude.
    - Fix GitLab CE incompatibilities #30.
  * 0.1.2: Fix parsing of GitLab versions #28.
  * 0.1.1: Fix failure to take into account group permissions #19.
  * 0.1.0: Initial release.
