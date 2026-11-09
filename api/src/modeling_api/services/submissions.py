"""Run-scoped submissions and human feedback, independent of editable models."""

import csv
import io
import json
from copy import deepcopy
from re import escape
from uuid import UUID

from lxml import etree
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from modeling_api.core.auth import User
from modeling_api.core.errors import ApiError, conflict, not_found
from modeling_api.db.client import db
from modeling_api.db.store import Document, insert, list_page, new_id, to_api, utcnow
from modeling_api.services.fbs_users import resolve_names
from modeling_api.schemas.submissions import (
    AssignmentData,
    PublishReviews,
    RunData,
    SaveAssignment,
    SaveGlobalFeedback,
    SaveReview,
    SaveRun,
    SetResolved,
    StartRun,
    SubmitModel,
)


def is_moderator(user: User) -> bool:
    return user.is_admin or user.global_role == "MODERATOR" or "MODERATOR" in user.roles


def require(condition: bool) -> None:
    if not condition:
        raise ApiError(403, "FORBIDDEN", "You do not have permission for this action.")


def rights(run: Document, user: User) -> Document:
    grant = next((g for g in run["data"]["grants"] if g["userId"] == user.id), {})
    all_rights = is_moderator(user) or run["createdBy"] == user.id
    return {
        key: all_rights or bool(grant.get(key))
        for key in ("manage", "review", "publish")
    }


def participant(run: Document, user: User) -> bool:
    return (
        user.is_admin
        or run["data"]["participation"] == "all"
        or user.id in run["data"]["participantIds"]
    )


def management_view(run: Document, user: User, view: str | None = None) -> bool:
    allowed = any(rights(run, user).values())
    if view == "management":
        require(allowed)
    return allowed and view != "participant"


async def submission_access(user: User) -> Document:
    delegated = await db.submission_runs.find_one(
        {
            "$or": [
                {"createdBy": user.id},
                {
                    "data.grants": {
                        "$elemMatch": {
                            "userId": user.id,
                            "$or": [
                                {"manage": True},
                                {"review": True},
                                {"publish": True},
                            ],
                        }
                    }
                },
            ]
        }
    )
    return {
        "canManage": is_moderator(user) or bool(delegated),
        "canCreate": is_moderator(user),
    }


async def courses(user: User) -> Document:
    """A learner catalog contains enrollment information, never configuration revisions."""
    assignments = await db.submission_assignments.find({}).sort("name", 1).to_list(None)
    runs = await db.submission_runs.find({}).to_list(None)
    members = await db.submission_participants.find({"userId": user.id}).to_list(None)
    memberships = {m["runId"]: m for m in members}
    current_ids = [m["submissionId"] for m in members if m.get("submissionId")]
    published = {
        r["submissionId"]
        for r in await db.submission_reviews.find(
            {"submissionId": {"$in": current_ids}, "publishedId": {"$ne": None}},
            {"submissionId": 1},
        ).to_list(None)
    }
    items = []
    for assignment in assignments:
        related = [run for run in runs if run["assignmentId"] == assignment["_id"]]
        visible = [
            run
            for run in related
            if bool(memberships.get(run["_id"], {}).get("history"))
            or run["_id"] == assignment.get("activeRunId")
            and not assignment["archived"]
            and run["data"]["state"] != "archived"
            and participant(run, user)
        ]
        if not visible:
            continue
        current = next(
            (r for r in visible if r["_id"] == assignment.get("activeRunId")), None
        )
        enrolled = bool(current and current["_id"] in memberships)
        items.append(
            {
                "id": assignment["_id"],
                "name": assignment["name"],
                "description": assignment["data"]["description"],
                "enrolled": enrolled,
                "deadline": current["data"]["deadline"] if current else None,
                "submissionStatus": (
                    "feedback_available"
                    if current
                    and memberships.get(current["_id"], {}).get("submissionId")
                    in published
                    else (
                        "submitted"
                        if current
                        and memberships.get(current["_id"], {}).get("submissionId")
                        else "not_submitted"
                    )
                ),
                "hasHistory": any(
                    memberships.get(r["_id"], {}).get("history") for r in visible
                ),
                "activeRunId": current["_id"] if current else None,
                "canEnroll": bool(
                    current
                    and not enrolled
                    and current["data"]["state"] == "open"
                    and current["data"]["deadline"] > utcnow()
                ),
            }
        )
    return {"items": items, **await submission_access(user)}


async def course_detail(identifier: UUID, user: User) -> Document:
    assignment = await load("submission_assignments", identifier)
    runs = (
        await db.submission_runs.find({"assignmentId": str(identifier)})
        .sort("createdAt", -1)
        .to_list(None)
    )
    members = await db.submission_participants.find(
        {"userId": user.id, "runId": {"$in": [r["_id"] for r in runs]}}
    ).to_list(None)
    memberships = {m["runId"]: m for m in members}
    visible = [
        r
        for r in runs
        if memberships.get(r["_id"], {}).get("history")
        or r["_id"] == assignment.get("activeRunId")
        and not assignment["archived"]
        and (participant(r, user) or any(rights(r, user).values()))
    ]
    require(bool(visible))
    return {
        "id": str(identifier),
        "name": assignment["name"],
        "description": assignment["data"]["description"],
        "activeRunId": assignment.get("activeRunId"),
        "canModerate": any(any(rights(r, user).values()) for r in runs),
        "runs": [
            {
                "id": r["_id"],
                "name": r["data"]["name"],
                "enrolled": r["_id"] in memberships,
            }
            for r in visible
        ],
    }


async def enroll(identifier: UUID, user: User) -> Document:
    run = await load("submission_runs", identifier)
    require(participant(run, user))
    assignment = await load("submission_assignments", run["assignmentId"])
    existing = await db.submission_participants.find_one(
        {"_id": f"{identifier}:{user.id}"}
    )
    if existing:
        return {"enrolled": True}
    if (
        assignment["archived"]
        or assignment.get("activeRunId") != str(identifier)
        or run["data"]["state"] != "open"
        or run["data"]["deadline"] <= utcnow()
    ):
        raise conflict("Enrollment is closed for this semester.")
    await db.submission_participants.update_one(
        {"_id": f"{identifier}:{user.id}"},
        {
            "$setOnInsert": {
                "runId": str(identifier),
                "userId": user.id,
                "submissionId": None,
                "reviewStarted": False,
                "history": [],
                "createdAt": utcnow(),
            }
        },
        upsert=True,
    )
    return {"enrolled": True}


async def load(collection: str, identifier) -> Document:
    document = await db[collection].find_one({"_id": str(identifier)})
    if not document:
        raise not_found()
    return document


async def known_users(ids: list[str]) -> None:
    if ids and await db.submission_users.count_documents(
        {"_id": {"$in": list(set(ids))}}
    ) != len(set(ids)):
        raise ApiError(422, "UNKNOWN_USER", "Choose users who have already signed in.")


async def users(
    user: User, q: str, run_id: UUID | None, bearer_token: str | None = None
) -> Document:
    if run_id:
        run = await load("submission_runs", run_id)
        require(rights(run, user)["manage"])
    else:
        require(is_moderator(user))
    query = (
        {
            "$or": [
                {"name": {"$regex": escape(q), "$options": "i"}},
                {"_id": {"$regex": escape(q), "$options": "i"}},
            ]
        }
        if q
        else {}
    )
    page = await list_page(
        db.submission_users, query, 0, 100, sort_field="name", sort_desc=False
    )
    names = await resolve_names(
        [item["id"] for item in page["items"]], user, bearer_token
    )
    for item in page["items"]:
        item["name"] = names[item["id"]]
    return page


def default_overlays() -> Document:
    return {
        key: {
            "image": {"src": src, "width": 26, "height": 26},
            "align": align,
            "verticalAlign": vertical,
            "offset": {"x": 0, "y": 0},
            "cursor": "pointer",
            "tooltip": label,
        }
        for key, src, align, vertical, label in (
            ("correct", "/images/checkmark.gif", "left", "top", "Correct"),
            ("incorrect", "/images/error.gif", "right", "top", "Incorrect"),
            ("hint", "/images/warning.gif", "right", "bottom", "Hint"),
        )
    }


async def global_feedback(revision: int | None = None) -> Document:
    settings = await db.submission_settings.find_one({"_id": "feedback"})
    if revision == 0 or not settings and revision is None:
        return {"revision": 0, "overlays": default_overlays()}
    if not settings:
        raise not_found()
    if revision is None or revision == settings["revision"]:
        return {"revision": settings["revision"], "overlays": settings["overlays"]}
    previous = next(
        (item for item in settings["history"] if item["revision"] == revision), None
    )
    if not previous:
        raise not_found()
    return previous


async def save_global_feedback(body: SaveGlobalFeedback, user: User) -> Document:
    require(user.is_admin)
    overlays = body.overlays.model_dump(mode="json", by_alias=True)
    for overlay in overlays.values():
        if overlay.get("icon"):
            continue
        src = overlay["image"]["src"]
        if not (
            src.startswith("/images/")
            and ".." not in src
            or src.startswith("data:image/png;base64,")
            or src.startswith("data:image/gif;base64,")
        ):
            raise ApiError(
                422, "INVALID_OVERLAY", "Use a local image or a PNG/GIF data URL."
            )
    previous = await global_feedback()
    if previous["revision"] != body.base_revision:
        raise conflict("Global settings changed. Reload before saving.")
    if body.base_revision == 0:
        try:
            await db.submission_settings.insert_one(
                {
                    "_id": "feedback",
                    "revision": 1,
                    "overlays": overlays,
                    "history": [previous],
                    "updatedBy": user.id,
                    "updatedAt": utcnow(),
                }
            )
        except DuplicateKeyError:
            raise conflict("Global settings changed. Reload before saving.") from None
    else:
        result = await db.submission_settings.update_one(
            {"_id": "feedback", "revision": body.base_revision},
            {
                "$set": {
                    "overlays": overlays,
                    "updatedBy": user.id,
                    "updatedAt": utcnow(),
                },
                "$inc": {"revision": 1},
                "$push": {"history": previous},
            },
        )
        if not result.modified_count:
            raise conflict("Global settings changed. Reload before saving.")
    return await global_feedback()


async def assignments(user: User, skip: int, limit: int, archived: bool) -> Document:
    query: Document = {"archived": archived}
    if not is_moderator(user):
        accessible = await db.submission_runs.find(
            {
                "$or": [
                    {"createdBy": user.id},
                    {
                        "data.grants": {
                            "$elemMatch": {
                                "userId": user.id,
                                "$or": [
                                    {"manage": True},
                                    {"review": True},
                                    {"publish": True},
                                ],
                            }
                        }
                    },
                ]
            },
            {"assignmentId": 1},
        ).to_list(None)
        query["_id"] = {"$in": list({run["assignmentId"] for run in accessible})}
    page = await list_page(
        db.submission_assignments, query, skip, limit, omit=("history",)
    )
    page["canCreate"] = is_moderator(user)
    return page


async def can_manage_assignment(assignment_id: str, user: User) -> bool:
    return is_moderator(user) or bool(
        await db.submission_runs.find_one(
            {
                "assignmentId": assignment_id,
                "data.state": {"$ne": "archived"},
                "$or": [
                    {"createdBy": user.id},
                    {
                        "data.grants": {
                            "$elemMatch": {"userId": user.id, "manage": True}
                        }
                    },
                ],
            }
        )
    )


async def save_assignment(
    identifier: UUID | None, body: SaveAssignment, user: User
) -> Document:
    data = body.model_dump(
        mode="json", by_alias=True, include=set(AssignmentData.model_fields)
    )
    reference = data.get("taskVersion")
    if reference and not await db.task_version.find_one(
        {
            "_id": reference["versionId"],
            "taskId": reference["taskId"],
            "kind": "release",
        }
    ):
        raise ApiError(422, "INVALID_TASK", "Choose an existing task release.")
    if identifier is None:
        require(is_moderator(user))
        return await insert(
            db.submission_assignments,
            {
                "data": data,
                "name": data["name"],
                "revision": 1,
                "archived": body.archived,
                "createdBy": user.id,
                "history": [],
            },
        )
    require(await can_manage_assignment(str(identifier), user))
    old = await load("submission_assignments", identifier)
    if old["revision"] != body.base_revision:
        raise conflict("The configuration changed. Reload before saving.")
    result = await db.submission_assignments.find_one_and_update(
        {"_id": str(identifier), "revision": body.base_revision},
        {
            "$set": {
                "data": data,
                "name": data["name"],
                "archived": body.archived,
                "updatedBy": user.id,
                "updatedAt": utcnow(),
            },
            "$inc": {"revision": 1},
            "$push": {
                "history": {
                    "revision": old["revision"],
                    "data": old["data"],
                    "archived": old["archived"],
                }
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if not result:
        raise conflict("The configuration changed. Reload before saving.")
    if body.archived:
        await archive_runs(str(identifier), user)
    return to_api(result)


async def assignment_detail(identifier: UUID, user: User) -> Document:
    assignment = await load("submission_assignments", identifier)
    runs = (
        await db.submission_runs.find({"assignmentId": str(identifier)})
        .sort("createdAt", -1)
        .to_list(None)
    )
    visible = [
        await run_info(run, user)
        for run in runs
        if is_moderator(user)
        or any(rights(run, user).values())
        or participant(run, user)
        or await db.submission_participants.find_one({"_id": f"{run['_id']}:{user.id}"})
    ]
    require(is_moderator(user) or bool(visible))
    return {
        **to_api(assignment),
        "runs": visible,
        "canManage": await can_manage_assignment(str(identifier), user),
    }


async def run_info(run: Document, user: User, view: str | None = None) -> Document:
    managing = management_view(run, user, view)
    permissions = (
        rights(run, user)
        if managing
        else {key: False for key in ("manage", "review", "publish")}
    )
    member = await db.submission_participants.find_one(
        {"_id": f"{run['_id']}:{user.id}"}
    )
    assignment = await load("submission_assignments", run["assignmentId"])
    accepting = (
        not assignment["archived"]
        and assignment.get("activeRunId") == run["_id"]
        and participant(run, user)
        and run["data"]["state"] == "open"
        and run["data"]["deadline"] > utcnow()
    )
    blocked_reason = (
        "archived"
        if run["data"]["state"] == "archived"
        or assignment.get("activeRunId") != run["_id"]
        else (
            "closed"
            if assignment["archived"] or run["data"]["state"] != "open"
            else (
                "deadline"
                if run["data"]["deadline"] <= utcnow()
                else (
                    "not_eligible"
                    if not participant(run, user)
                    else (
                        "not_enrolled"
                        if not member
                        else "review_started" if member["reviewStarted"] else None
                    )
                )
            )
        )
    )
    public = {k: v for k, v in run.items() if k not in ("history", "data")}
    data = (
        run["data"]
        if permissions["manage"]
        else {
            k: v
            for k, v in run["data"].items()
            if k not in ("grants", "participantIds")
        }
    )
    return {
        **to_api(public),
        "data": data,
        "permissions": permissions,
        "canSubmit": bool(accepting and member and not member["reviewStarted"]),
        "enrolled": bool(member),
        "canEnroll": bool(accepting and not member),
        "canModerate": any(rights(run, user).values()),
        "managementView": managing,
        "submissionBlockedReason": blocked_reason,
    }


async def run_detail(identifier: UUID, user: User, view: str | None = None) -> Document:
    run = await load("submission_runs", identifier)
    require(
        any(rights(run, user).values())
        or participant(run, user)
        or bool(
            await db.submission_participants.find_one(
                {"_id": f"{identifier}:{user.id}"}
            )
        )
    )
    assignment = await load("submission_assignments", run["assignmentId"])
    version = (
        assignment
        if assignment["revision"] == run["assignmentRevision"]
        else next(
            v
            for v in assignment["history"]
            if v["revision"] == run["assignmentRevision"]
        )
    )
    result = {**await run_info(run, user, view), "assignment": version["data"]}
    if management_view(run, user, view) and rights(run, user)["manage"]:
        result["history"] = run.get("history", [])
    return result


def run_data(body: RunData) -> Document:
    return body.model_dump(
        mode="python", by_alias=True, include=set(RunData.model_fields)
    )


async def start_run(assignment_id: UUID, body: StartRun, user: User) -> Document:
    require(await can_manage_assignment(str(assignment_id), user))
    assignment = await load("submission_assignments", assignment_id)
    if assignment["archived"] or assignment["revision"] != body.assignment_revision:
        raise conflict(
            "Reload the active assignment configuration before starting a run."
        )
    await known_users(body.participant_ids + [g.user_id for g in body.grants])
    if body.deadline <= utcnow():
        raise ApiError(422, "INVALID_DEADLINE", "The deadline must be in the future.")
    earlier = await db.submission_runs.find(
        {"assignmentId": str(assignment_id), "data.state": {"$ne": "archived"}},
        {"_id": 1},
    ).to_list(None)
    identifier = new_id()
    claimed = await db.submission_assignments.update_one(
        {
            "_id": str(assignment_id),
            "revision": assignment["revision"],
            "archived": False,
            "activeRunId": assignment.get("activeRunId"),
        },
        {"$set": {"activeRunId": identifier}},
    )
    if not claimed.modified_count:
        raise conflict("Another run was started. Reload before starting a run.")
    # Runs are independent: starting a semester never moves or deletes earlier data.
    try:
        run = await insert(
            db.submission_runs,
            {
                "_id": identifier,
                "assignmentId": str(assignment_id),
                "assignmentRevision": assignment["revision"],
                "revision": 1,
                "data": run_data(body),
                "history": [],
                "createdBy": user.id,
            },
        )
    except Exception:
        await db.submission_assignments.update_one(
            {"_id": str(assignment_id), "activeRunId": identifier},
            {"$set": {"activeRunId": assignment.get("activeRunId")}},
        )
        raise
    await archive_runs(
        str(assignment_id), user, identifiers=[item["_id"] for item in earlier]
    )
    return await run_detail(UUID(run["id"]), user)


async def archive_runs(
    assignment_id: str, user: User, identifiers: list[str] | None = None
) -> None:
    query: Document = {"assignmentId": assignment_id, "data.state": {"$ne": "archived"}}
    if identifiers is not None:
        query["_id"] = {"$in": identifiers}
    for run in await db.submission_runs.find(query).to_list(None):
        changed = await db.submission_runs.update_one(
            {"_id": run["_id"], "revision": run["revision"]},
            {
                "$set": {
                    "data.state": "archived",
                    "updatedAt": utcnow(),
                    "updatedBy": user.id,
                },
                "$inc": {"revision": 1},
                "$push": {
                    "history": {
                        "revision": run["revision"],
                        "data": run["data"],
                        "at": utcnow(),
                        "by": user.id,
                    }
                },
            },
        )
        if not changed.modified_count:
            raise conflict(
                "A previous run changed while archiving. Reload the run overview."
            )


async def save_run(identifier: UUID, body: SaveRun, user: User) -> Document:
    run = await load("submission_runs", identifier)
    require(rights(run, user)["manage"])
    if run["revision"] != body.base_revision:
        raise conflict("The run changed. Reload before saving.")
    if run["data"]["state"] == "archived":
        raise conflict("Archived runs are read only. Start a new named run instead.")
    assignment = await load("submission_assignments", run["assignmentId"])
    if body.state != "archived" and (
        assignment["archived"] or assignment.get("activeRunId") != str(identifier)
    ):
        raise conflict(
            "Earlier runs are archived. Start a new named run to reuse the configuration."
        )
    await known_users(body.participant_ids + [g.user_id for g in body.grants])
    result = await db.submission_runs.find_one_and_update(
        {"_id": str(identifier), "revision": body.base_revision},
        {
            "$set": {
                "data": run_data(body),
                "updatedBy": user.id,
                "updatedAt": utcnow(),
            },
            "$inc": {"revision": 1},
            "$push": {
                "history": {
                    "revision": run["revision"],
                    "data": run["data"],
                    "at": utcnow(),
                    "by": user.id,
                }
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if not result:
        raise conflict("The run changed. Reload before saving.")
    return await run_detail(identifier, user)


def validate_package(package: Document) -> list[str]:
    """Validate independently of the browser; never accept XML entities or duplicate IDs."""
    if len(json.dumps(package).encode()) > 12 * 1024 * 1024:
        raise ApiError(
            422, "PACKAGE_TOO_LARGE", "Submission packages are limited to 12 MB."
        )
    try:
        if package["format"] != "modeling-copilot-model" or package["version"] != 1:
            raise ValueError()
        xml = package["model"]["xml"]
        if (
            not isinstance(xml, str)
            or "<!DOCTYPE" in xml.upper()
            or "<!ENTITY" in xml.upper()
        ):
            raise ValueError()
        root = etree.fromstring(
            xml.encode(), etree.XMLParser(resolve_entities=False, no_network=True)
        )
        if root.tag != "GraphDataModel":
            raise ValueError()
        cells = root.findall("./root/Cell")
        by_id = {cell.get("id"): cell for cell in cells}
        if not cells or len(by_id) != len(cells) or None in by_id or "" in by_id:
            raise ValueError()
        if any(not cid.strip() or len(cid) > 256 for cid in by_id):
            raise ValueError()
        roots = [cell for cell in cells if not cell.get("parent")]
        if len(roots) != 1:
            raise ValueError()
        for cell in cells:
            for key in ("parent", "source", "target"):
                if cell.get(key) and cell.get(key) not in by_id:
                    raise ValueError()
            seen = set()
            current = cell
            while current is not None:
                cid = current.get("id")
                if cid in seen:
                    raise ValueError()
                seen.add(cid)
                current = by_id.get(current.get("parent"))
        definitions = {
            (lang["languageId"], lang["versionId"]): lang
            for lang in package["languages"]
        }
        if len(definitions) != len(package["languages"]):
            raise ValueError()
        visited, active = set(), set()

        def check_definition(definition):
            if (
                not isinstance(definition, dict)
                or not isinstance(definition.get("type"), str)
                or not definition["type"].strip()
                or not isinstance(definition.get("style"), dict)
            ):
                raise ValueError()
            children = definition.get("children", [])
            if not isinstance(children, list):
                raise ValueError()
            for child in children:
                check_definition(child)

        def visit(reference):
            key = (reference["languageId"], reference["versionId"])
            if key in active or key not in definitions:
                raise ValueError()
            if key in visited:
                return
            active.add(key)
            lang = definitions[key]
            if not isinstance(lang.get("name"), str) or not lang["name"].strip():
                raise ValueError()
            for field in ("elements", "connections", "syntax"):
                if not isinstance(lang["data"][field], list):
                    raise ValueError()
            for definition in lang["data"]["elements"] + lang["data"]["connections"]:
                check_definition(definition)
            for included in lang["includedLanguageVersions"]:
                visit(included)
            active.remove(key)
            visited.add(key)

        refs = package["workspaceLanguages"]
        if len({ref["languageId"] for ref in refs}) != len(refs):
            raise ValueError()
        for reference in refs:
            visit(reference)
        if visited != set(definitions):
            raise ValueError()
        # Do not allow feedback targeting graph roots, layers or legacy feedback objects.
        layers = {
            cell.get("id") for cell in cells if cell.get("parent") == roots[0].get("id")
        }
        eligible = []
        ordered_layers = [c for c in cells if c.get("parent") == roots[0].get("id")]
        model_layer = ordered_layers[0].get("id") if ordered_layers else None
        for cell in cells:
            current = cell
            while current.get("parent") and current.get("parent") not in layers:
                current = by_id[current.get("parent")]
            if current.get("parent") == model_layer and (
                cell.get("vertex") == "1" or cell.get("edge") == "1"
            ):
                eligible.append(cell.get("id"))
        return eligible
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        RecursionError,
        etree.XMLSyntaxError,
    ):
        raise ApiError(
            422, "INVALID_PACKAGE", "The model package is invalid or incomplete."
        ) from None


async def package_saved_model(body: SubmitModel, user: User) -> Document:
    from modeling_api.services.models import get_version

    version = await get_version(body.model_id, body.version_id, user)
    references = version.get("workspaceLanguages", [])
    languages, visited = [], set()

    async def include(reference):
        key = (reference["languageId"], reference["versionId"])
        if key in visited:
            return
        visited.add(key)
        language = await load("languages", key[0])
        definition = await load("language_versions", key[1])
        if definition["languageId"] != key[0]:
            raise not_found()
        languages.append(
            {
                "languageId": key[0],
                "versionId": key[1],
                "name": language["name"],
                "data": definition["data"],
                "includedLanguageVersions": definition.get(
                    "includedLanguageVersions", []
                ),
            }
        )
        for child in definition.get("includedLanguageVersions", []):
            await include(child)

    for reference in references:
        await include(reference)
    return {
        "format": "modeling-copilot-model",
        "version": 1,
        "model": {"xml": version["data"].get("xml", "")},
        "workspaceLanguages": references,
        "languages": languages,
    }


async def submit(run_id: UUID, body: SubmitModel, user: User) -> Document:
    run = await load("submission_runs", run_id)
    require(participant(run, user))
    assignment = await load("submission_assignments", run["assignmentId"])
    if assignment["archived"]:
        raise conflict("This assignment has been archived.")
    if assignment.get("activeRunId") != str(run_id):
        raise conflict("This run is no longer the active run.")
    if run["data"]["state"] != "open" or run["data"]["deadline"] <= utcnow():
        raise conflict("This run is closed or its deadline has passed.")
    package = (
        body.package
        if body.package is not None
        else await package_saved_model(body, user)
    )
    target_ids = validate_package(package)
    source_model = (
        await db.models.find_one(
            {"_id": str(body.model_id), "ownerId": user.id}, {"name": 1}
        )
        if body.model_id
        else None
    )
    model_name = (
        source_model["name"] if source_model else body.model_name or "Uploaded model"
    )
    key = f"{run_id}:{user.id}"
    member = await db.submission_participants.find_one({"_id": key})
    if not member:
        raise conflict("Enroll in this course before submitting a model.")
    if member and (
        member["reviewStarted"]
        or member["submissionId"]
        != (str(body.base_submission_id) if body.base_submission_id else None)
    ):
        raise conflict("The submission changed or its review has already started.")
    if not member and body.base_submission_id:
        raise conflict("Reload before submitting.")
    # Confirm run revision again after materializing/validating the model.
    if not await db.submission_runs.find_one(
        {
            "_id": str(run_id),
            "revision": run["revision"],
            "data.state": "open",
            "data.deadline": {"$gt": utcnow()},
        }
    ):
        raise conflict("The run changed or closed. Reload before submitting.")
    saved = await insert(
        db.submissions,
        {
            "runId": str(run_id),
            "ownerId": user.id,
            "package": package,
            "modelName": model_name,
            "targetIds": target_ids,
            "sourceModelId": str(body.model_id) if body.model_id else None,
            "sourceVersionId": str(body.version_id) if body.version_id else None,
            "revision": 1,
        },
    )
    if member:
        result = await db.submission_participants.update_one(
            {
                "_id": key,
                "submissionId": member["submissionId"],
                "reviewStarted": False,
            },
            {"$set": {"submissionId": saved["id"]}, "$push": {"history": saved["id"]}},
        )
        if not result.modified_count:
            raise conflict(
                "The submission changed or its review started. Reload before submitting."
            )
    else:
        try:
            await db.submission_participants.insert_one(
                {
                    "_id": key,
                    "runId": str(run_id),
                    "userId": user.id,
                    "submissionId": saved["id"],
                    "reviewStarted": False,
                    "history": [saved["id"]],
                    "createdAt": utcnow(),
                }
            )
        except DuplicateKeyError:
            raise conflict(
                "A submission was already received. Reload before submitting."
            ) from None
    return await submission_detail(UUID(saved["id"]), user, "participant")


async def accessible_submission(
    identifier: UUID, user: User
) -> tuple[Document, Document]:
    submission = await load("submissions", identifier)
    run = await load("submission_runs", submission["runId"])
    require(submission["ownerId"] == user.id or any(rights(run, user).values()))
    member = await db.submission_participants.find_one(
        {"_id": f"{run['_id']}:{submission['ownerId']}", "history": str(identifier)}
    )
    if not member:
        raise not_found()
    return submission, run


def review_permissions(submission: Document, run: Document, user: User) -> bool:
    return (
        run["data"]["state"] != "archived"
        and (submission["ownerId"] != user.id or user.is_admin)
        and rights(run, user)["review"]
    )


async def review_info(review: Document, staff: bool) -> Document:
    result = {k: v for k, v in review.items() if k not in ("entries", "score")}
    if staff and review["kind"] == "staff":
        result["entries"] = review["entries"]
        result["score"] = review.get("score")
    if review.get("publishedId"):
        result["published"] = to_api(
            await load("submission_publications", review["publishedId"])
        )
    return to_api(result)


async def submission_detail(
    identifier: UUID,
    user: User,
    view: str | None = None,
    bearer_token: str | None = None,
) -> Document:
    submission, run = await accessible_submission(identifier, user)
    if view == "participant":
        require(submission["ownerId"] == user.id)
    staff = management_view(run, user, view)
    permissions = (
        rights(run, user)
        if staff
        else {key: False for key in ("manage", "review", "publish")}
    )
    can_review = review_permissions(submission, run, user)
    can_review = can_review and staff
    reviews = (
        await db.submission_reviews.find({"submissionId": str(identifier)})
        .sort("createdAt", 1)
        .to_list(None)
    )
    visible = [
        await review_info(review, staff)
        for review in reviews
        if (review["kind"] == "staff" and staff)
        or review.get("publishedId")
        and (staff or submission["ownerId"] == user.id)
    ]
    resolved = await db.submission_resolutions.find(
        {"submissionId": str(identifier), "userId": user.id, "resolved": True}
    ).to_list(None)
    member = await db.submission_participants.find_one(
        {"_id": f"{run['_id']}:{submission['ownerId']}"}
    )
    result = {k: v for k, v in submission.items() if k not in ("targetIds", "peerIds")}
    actor_ids = {submission["ownerId"]}
    for review in visible:
        for entry in [
            *review.get("entries", []),
            *review.get("published", {}).get("entries", []),
        ]:
            actor_ids.update(
                value
                for value in (entry.get("createdBy"), entry.get("updatedBy"))
                if value
            )
        if review.get("reviewerId"):
            actor_ids.add(review["reviewerId"])
    people = await resolve_names(actor_ids, user, bearer_token)
    return {
        **to_api(result),
        "reviews": visible,
        "resolved": [r["entryKey"] for r in resolved],
        "permissions": {**permissions, "review": can_review},
        "isOwner": submission["ownerId"] == user.id,
        "current": member["submissionId"] == str(identifier),
        "reviewStarted": member["reviewStarted"],
        "runState": run["data"]["state"],
        "assignmentId": run["assignmentId"],
        "managementView": staff,
        "canModerate": any(rights(run, user).values()),
        "people": people,
    }


async def export_submissions_csv(
    run_id: UUID, user: User, bearer_token: str | None = None
) -> str:
    run = await load("submission_runs", run_id)
    require(any(rights(run, user).values()))
    rows = (
        await db.submissions.find({"runId": str(run_id)}, {"ownerId": 1})
        .sort([("createdAt", 1), ("_id", 1)])
        .to_list(None)
    )
    owner_ids = {row["ownerId"] for row in rows}
    names = await resolve_names(owner_ids, user, bearer_token)
    contacts = {
        item["_id"]: item.get("email") or ""
        for item in await db.submission_users.find(
            {"_id": {"$in": list(owner_ids)}}, {"email": 1}
        ).to_list(None)
    }

    reviews = await db.submission_reviews.find(
        {"runId": str(run_id), "kind": "staff"}
    ).to_list(None)
    scores = {review["submissionId"]: review.get("score") for review in reviews}
    publications = await db.submission_publications.find(
        {
            "_id": {
                "$in": [
                    review["publishedId"]
                    for review in reviews
                    if review.get("publishedId")
                ]
            }
        },
        {"submissionId": 1, "score": 1},
    ).to_list(None)
    published_scores = {item["submissionId"]: item.get("score") for item in publications}

    def csv_value(value: str) -> str:
        # Quoting alone does not prevent spreadsheet formula execution.
        if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(
            ("=", "+", "-", "@")
        ):
            return "'" + value
        return value

    output = io.StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        ["ID", "Student name", "Email", "Overall score (%)", "Published score (%)"]
    )
    for row in rows:
        owner_id = row["ownerId"]
        writer.writerow(
            [
                csv_value(value)
                for value in (
                    owner_id,
                    names.get(owner_id, owner_id),
                    contacts.get(owner_id, ""),
                    str(scores[row["_id"]]) if scores.get(row["_id"]) is not None else "",
                    str(published_scores[row["_id"]])
                    if published_scores.get(row["_id"]) is not None
                    else "",
                )
            ]
        )
    return output.getvalue()


async def submission_list(
    run_id: UUID,
    user: User,
    skip: int,
    limit: int,
    history: bool,
    view: str | None = None,
    bearer_token: str | None = None,
) -> Document:
    run = await load("submission_runs", run_id)
    await run_detail(run_id, user)
    query: Document = {"runId": str(run_id)}
    managing = management_view(run, user, view)
    if view == "participant":
        query["ownerId"] = user.id
    elif not managing:
        query["ownerId"] = user.id
    members = await db.submission_participants.find({"runId": str(run_id)}).to_list(
        None
    )
    accepted = [
        sid
        for member in members
        for sid in (member["history"] if history else [member["submissionId"]])
    ]
    query["_id"] = {"$in": accepted}
    page = await list_page(
        db.submissions, query, skip, limit, omit=("package", "targetIds", "peerIds")
    )
    people = await resolve_names(
        {item["ownerId"] for item in page["items"]}, user, bearer_token
    )
    for item in page["items"]:
        item["ownerName"] = people.get(item["ownerId"], item["ownerId"])
        reviews = await db.submission_reviews.find(
            {"submissionId": item["id"]}
        ).to_list(None)
        visible = managing
        item["reviews"] = [
            {
                "id": r["_id"],
                "revision": r["revision"],
                "status": r["status"],
                "kind": r["kind"],
                "reviewerId": r["reviewerId"],
            }
            for r in reviews
            if visible and r["kind"] == "staff"
        ]
        active_reviews = [review for review in reviews if review["kind"] == "staff"]
        item["status"] = (
            "feedback_available"
            if any(r.get("publishedId") for r in reviews)
            else (
                "reviewed"
                if active_reviews
                and all(r["status"] == "complete" for r in active_reviews)
                else "in_review" if active_reviews else "submitted"
            )
        )
        if not visible:
            item["status"] = (
                "feedback_available"
                if any(r.get("publishedId") for r in reviews)
                else "submitted"
            )
        item["current"] = any(m["submissionId"] == item["id"] for m in members)
        item["reviewStarted"] = any(
            m["submissionId"] == item["id"] and m["reviewStarted"] for m in members
        )
    return page


async def save_review(
    identifier: UUID, body: SaveReview, user: User, kind: str, view: str | None = None
) -> Document:
    submission, run = await accessible_submission(identifier, user)
    staff = review_permissions(submission, run, user)
    if view == "participant":
        staff = False
    require(staff and kind == "staff")
    if body.action == "complete" and body.score is None:
        raise ApiError(
            422,
            "SCORE_REQUIRED",
            "Enter an overall score from 0 to 100 before finishing the review.",
        )
    review_id = f"{identifier}:staff"
    previous = await db.submission_reviews.find_one({"_id": review_id})
    if (previous["revision"] if previous else 0) != body.base_revision:
        raise conflict("This review changed. Reload before saving.")
    if body.action == "reopen" and not previous:
        raise conflict("There is no completed review to reopen.")
    ids, states, entries = set(), set(), []
    old_entries = {item["id"]: item for item in previous["entries"]} if previous else {}
    now = utcnow()
    for item in body.entries:
        entry = item.model_dump(mode="python", by_alias=True)
        entry["id"] = str(item.id)
        if (
            entry["cellId"] not in submission["targetIds"]
            or entry["id"] in ids
            or (entry["cellId"], entry["state"]) in states
        ):
            raise ApiError(
                422,
                "INVALID_TARGET",
                "Feedback must reference a unique marking on an existing model object.",
            )
        if entry["state"] in ("correct", "incorrect") and any(
            (entry["cellId"], state) in states for state in ("correct", "incorrect")
        ):
            raise ApiError(
                422,
                "CONFLICTING_MARKINGS",
                "An object cannot be both correct and incorrect in one review.",
            )
        ids.add(entry["id"])
        states.add((entry["cellId"], entry["state"]))
        old = old_entries.get(entry["id"])
        entry["createdBy"] = old["createdBy"] if old else user.id
        if old and all(
            old.get(key) == entry[key] for key in ("cellId", "state", "comment")
        ):
            entry.update({key: old[key] for key in ("updatedBy", "updatedAt")})
        else:
            entry.update(updatedBy=user.id, updatedAt=now)
        entries.append(entry)
    # One atomic participant update arbitrates replacement versus first review.
    frozen = await db.submission_participants.update_one(
        {
            "_id": f"{run['_id']}:{submission['ownerId']}",
            "submissionId": str(identifier),
        },
        {"$set": {"reviewStarted": True}},
    )
    if not frozen.matched_count:
        raise conflict("This submission was replaced. Open the current submission.")
    settings = await global_feedback(previous["configRevision"] if previous else None)
    fields = {
        "entries": entries,
        "score": body.score,
        "status": "complete" if body.action == "complete" else "draft",
        "updatedAt": now,
        "updatedBy": user.id,
    }
    if not previous:
        try:
            await db.submission_reviews.insert_one(
                {
                    "_id": review_id,
                    "submissionId": str(identifier),
                    "runId": run["_id"],
                    "kind": kind,
                    "reviewerId": None,
                    "revision": 1,
                    "configRevision": settings["revision"],
                    "createdAt": now,
                    "publishedId": None,
                    "publication": 0,
                    **fields,
                }
            )
        except DuplicateKeyError:
            raise conflict("This review changed. Reload before saving.") from None
    else:
        changed = await db.submission_reviews.update_one(
            {"_id": review_id, "revision": body.base_revision},
            {"$set": fields, "$inc": {"revision": 1}},
        )
        if not changed.modified_count:
            raise conflict("This review changed. Reload before saving.")
    return await submission_detail(identifier, user, view)


async def publish(run_id: UUID, body: PublishReviews, user: User) -> Document:
    run = await load("submission_runs", run_id)
    require(rights(run, user)["publish"] and run["data"]["state"] != "archived")
    results = []
    for requested in body.reviews:
        review = await db.submission_reviews.find_one(
            {
                "_id": requested.review_id,
                "runId": str(run_id),
                "submissionId": str(requested.submission_id),
                "revision": requested.revision,
                "status": "complete",
                "kind": "staff",
            }
        )
        if not review or review.get("score") is None:
            results.append(
                {
                    "reviewId": requested.review_id,
                    "published": False,
                    "message": "Review changed, is not complete or has no overall score.",
                }
            )
            continue
        submission = await load("submissions", requested.submission_id)
        if submission["ownerId"] == user.id and not user.is_admin:
            results.append(
                {
                    "reviewId": requested.review_id,
                    "published": False,
                    "message": "You cannot release feedback for your own submission.",
                }
            )
            continue
        publication = await insert(
            db.submission_publications,
            {
                "reviewId": review["_id"],
                "submissionId": str(requested.submission_id),
                "runId": str(run_id),
                "number": review["publication"] + 1,
                "entries": deepcopy(review["entries"]),
                "score": review["score"],
                "configRevision": review["configRevision"],
                "publishedBy": user.id,
            },
        )
        changed = await db.submission_reviews.update_one(
            {
                "_id": review["_id"],
                "revision": requested.revision,
                "status": "complete",
            },
            {
                "$set": {
                    "publishedId": publication["id"],
                    "publication": publication["number"],
                    "status": "published",
                },
                "$inc": {"revision": 1},
            },
        )
        results.append(
            {
                "reviewId": review["_id"],
                "published": bool(changed.modified_count),
                "message": (
                    "Published."
                    if changed.modified_count
                    else "Review changed. Reload before releasing."
                ),
            }
        )
    return {"items": results}


async def resolve(identifier: UUID, body: SetResolved, user: User) -> Document:
    submission, _run = await accessible_submission(identifier, user)
    require(submission["ownerId"] == user.id)
    review = await load("submission_reviews", body.review_id)
    if review["submissionId"] != str(identifier) or not review.get("publishedId"):
        raise not_found()
    publication = await load("submission_publications", review["publishedId"])
    if publication["number"] != body.publication:
        raise conflict("New feedback is available. Reload before changing its status.")
    entry = next(
        (
            entry
            for entry in publication["entries"]
            if entry["id"] == str(body.entry_id)
        ),
        None,
    )
    require(bool(entry) and entry["state"] != "correct")
    key = f"{body.review_id}:{body.publication}:{body.entry_id}"
    await db.submission_resolutions.update_one(
        {"_id": f"{user.id}:{key}"},
        {
            "$set": {
                "submissionId": str(identifier),
                "runId": submission["runId"],
                "userId": user.id,
                "entryKey": key,
                "resolved": body.resolved,
                "updatedAt": utcnow(),
            }
        },
        upsert=True,
    )
    return {"entryKey": key, "resolved": body.resolved}
