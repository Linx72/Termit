ROLE_RANK = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}


def required_role(method: str, path: str) -> str:
    if path.startswith("/api/feedback"):
        return "viewer"
    if path.startswith("/api/eval"):
        return "operator"
    if path.startswith("/api/retrieval") and method == "POST":
        return "operator"
    if path.startswith("/api/retrieval"):
        return "viewer"
    if path.startswith("/api/ops/incident-drill") and method == "POST":
        return "admin"
    if path.startswith("/api/ops/quota") and method == "POST":
        return "admin"
    if path.startswith("/api/ops/quota-summary") and method == "GET":
        return "admin"
    if path.startswith("/api/ops/agent-runs"):
        return "admin"
    if path.startswith("/api/tools/execute") and method == "POST":
        return "operator"
    if path.startswith("/api/tools/audit") and method == "GET":
        return "admin"
    if path.startswith("/api/tasks") and method in {"POST", "DELETE"}:
        return "operator"
    if path.startswith("/api/tasks") and method == "GET":
        return "viewer"
    if path.startswith("/api/automation") and method == "POST":
        return "operator"
    if path.startswith("/api/local") and method == "POST":
        return "operator"
    if path.startswith("/api/local"):
        return "viewer"
    if path.startswith("/api/agents") and method == "POST":
        return "operator"
    if path.startswith("/api/agents"):
        return "viewer"
    if path.startswith("/api/orchestration") and method == "POST":
        return "operator"
    if path.startswith("/api/teams"):
        return "viewer"
    if path.startswith("/api/routing"):
        return "viewer"
    if path.startswith("/api/finetune") and method == "POST":
        return "operator"
    if path.startswith("/api/finetune"):
        return "viewer"
    if path.startswith("/api/sessions") and method == "DELETE":
        return "admin"
    return "viewer"


def role_allows(role: str, method: str, path: str) -> bool:
    normalized_role = role if role in ROLE_RANK else "viewer"
    required = required_role(method, path)
    return ROLE_RANK[normalized_role] >= ROLE_RANK[required]
