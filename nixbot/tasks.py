import logging

from . import app, celery
from .helper import gh_login
from .hydra_jobsets import HydraJobsets
from .pr_merge import merge_push

log = logging.getLogger(__name__)


@celery.task()
def github_comment(args, pr_info, body):
    owner, repo, number = pr_info
    gh = gh_login(app.config.get('NIXBOT_GITHUB_TOKEN'))
    pr = gh.get_repo(f'{owner}/{repo}').get_pull(number)
    log.info(f'Comment on PR {pr.number}: ' + body.format(*args))
    if app.config.get('NIXBOT_GITHUB_WRITE_COMMENTS'):
        pr.create_issue_comment(body.format(*args))


@celery.task()
def test_github_pr(pr_info):
    gh = gh_login(app.config.get('NIXBOT_GITHUB_TOKEN'))
    pr = gh.get_repo(f'{owner}/{repo}').get_pull(number)
    merge_push_task.delay(pr_info, pr.base.ref)


@celery.task
def add_hydra_jobset(pr_id):
    jobsets = HydraJobsets(app.config)
    jobsets.add(pr_id)

    return ['URL']


@celery.task
def merge_push_task(pr_info, base):
    owner, repo, number = pr_info
    merge_push(number, base, app.config)
    (add_hydra_jobset.s(pr_id) |
        github_comment.s(pr_info, 'Jobset created at {}'))()

@celery.task
def issue_commented(payload):
    bot_name = app.config.get('NIXBOT_BOT_NAME')
    if payload.get("action") not in ["created", "edited"]:
        return

    comment = payload['comment']['body'].strip()
    if comment == (f'@{bot_name} build'):
        # TODO: this should ignore issues
        pr_info = (
            payload["repository"]["owner"]["login"],
            payload["repository"]["name"],
            payload["issue"]["number"]
        )
        gh = gh_login(app.config.get('NIXBOT_GITHUB_TOKEN'))
        repo = gh.get_repo(app.config.get('NIXBOT_REPO'))
        if repo.has_in_collaborators(payload["comment"]["user"]["login"]):
            test_github_pr.delay(pr_info)
        else:
            github_comment.delay((), pr_info, f'@{payload["comment"]["user"]["login"]} is not a committer')
