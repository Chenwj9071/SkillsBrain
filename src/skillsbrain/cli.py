"""SkillsBrain CLI。"""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests
import typer
from typer import BadParameter

from skillsbrain.runtime import (
    SERVICE_NAME,
    get_runtime_file,
    is_pid_running,
    is_port_open,
    now_iso,
    read_runtime_file,
    remove_runtime_file,
    terminate_pid,
    wait_for_pid_exit,
    write_runtime_file,
)

app = typer.Typer(
    name="skillsbrain",
    help="Local skill routing engine for AI Agents",
    add_completion=False,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DATA_DIR = Path.home() / ".skillsbrain"
DEFAULT_SKILLS_DIR = DEFAULT_DATA_DIR / "skills"
DEFAULT_INDEX_DIR = DEFAULT_DATA_DIR / ".index"
DEFAULT_LOG_DIR = DEFAULT_DATA_DIR / "logs"
DEFAULT_SUBSCRIPTIONS_FILE = DEFAULT_INDEX_DIR / "subscriptions.json"
STARTUP_TIMEOUT_SECONDS = 120.0
STOP_TIMEOUT_SECONDS = 20.0


def resolve_base_dir(data_dir: Path | None) -> Path:
    return data_dir.resolve() if data_dir else DEFAULT_DATA_DIR.resolve()


def get_server_url(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    return f"http://{host}:{port}"


def request_json(method: str, url: str, **kwargs):
    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        typer.secho("Error: Cannot connect to SkillsBrain server.", fg="red")
        raise typer.Exit(1)
    except requests.exceptions.Timeout:
        typer.secho("Error: Request to SkillsBrain timed out.", fg="red")
        raise typer.Exit(1)
    except requests.exceptions.HTTPError as exc:
        detail = exc.response.text.strip() if exc.response is not None else str(exc)
        status_code = exc.response.status_code if exc.response is not None else "error"
        typer.secho(f"Error: SkillsBrain returned HTTP {status_code}.", fg="red")
        if detail:
            typer.echo(detail)
        raise typer.Exit(1)
    except requests.exceptions.RequestException as exc:
        typer.secho(f"Error: Request failed: {exc}", fg="red")
        raise typer.Exit(1)

    try:
        return response.json()
    except ValueError:
        typer.secho("Error: SkillsBrain returned invalid JSON.", fg="red")
        raise typer.Exit(1)


def try_request_json(method: str, url: str, **kwargs) -> Any | None:
    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, ValueError):
        return None


def build_server_env(base_dir: Path, skills_dir: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    env["SKILLSBRAIN_INDEX_DIR"] = str((base_dir / ".index").resolve())
    env["SKILLSBRAIN_LOG_DIR"] = str((base_dir / "logs").resolve())
    env["SKILLSBRAIN_SUBSCRIPTIONS_FILE"] = str((base_dir / ".index" / "subscriptions.json").resolve())
    src_root = Path(__file__).resolve().parents[1]
    current_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_parts = [part for part in current_pythonpath.split(os.pathsep) if part]
    if str(src_root) not in pythonpath_parts:
        pythonpath_parts.insert(0, str(src_root))
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    if skills_dir:
        env["SKILLSBRAIN_SKILLS_DIR"] = str(skills_dir.resolve())
    else:
        env["SKILLSBRAIN_SKILLS_DIR"] = str((base_dir / "skills").resolve())
    return env


def probe_admin_status(host: str, port: int, timeout: float = 1.0) -> dict[str, Any] | None:
    url = f"{get_server_url(host, port)}/api/admin/status"
    return try_request_json("GET", url, timeout=timeout)


def wait_until_ready(host: str, port: int, timeout_seconds: float, process: subprocess.Popen | None = None) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"SkillsBrain exited unexpectedly with code {process.returncode}.")

        status = probe_admin_status(host, port, timeout=1.0)
        if status:
            last_status = status
            if status.get("service") == SERVICE_NAME and status.get("ready") is True:
                return status
        time.sleep(0.5)

    if last_status is not None:
        raise RuntimeError(f"SkillsBrain did not become ready in time. Last status: {last_status.get('status', 'unknown')}")
    raise RuntimeError("SkillsBrain did not become ready in time.")


def load_runtime(base_dir: Path) -> tuple[Path, dict[str, Any] | None]:
    runtime_file = get_runtime_file(base_dir)
    return runtime_file, read_runtime_file(runtime_file)


def cleanup_stale_runtime(runtime_file: Path, runtime: dict[str, Any] | None) -> None:
    if runtime is None:
        remove_runtime_file(runtime_file)
        return

    pid = runtime.get("pid")
    host = runtime.get("host", DEFAULT_HOST)
    port = runtime.get("port", DEFAULT_PORT)
    pid_alive = isinstance(pid, int) and is_pid_running(pid)
    status = probe_admin_status(host, port, timeout=0.5)
    if not pid_alive and status is None:
        remove_runtime_file(runtime_file)


def ensure_not_running(base_dir: Path, host: str, port: int) -> None:
    runtime_file, runtime = load_runtime(base_dir)
    cleanup_stale_runtime(runtime_file, runtime)
    runtime = read_runtime_file(runtime_file)
    if runtime:
        pid = runtime.get("pid")
        current_host = runtime.get("host", host)
        current_port = runtime.get("port", port)
        status = probe_admin_status(current_host, current_port, timeout=0.5)
        if (isinstance(pid, int) and is_pid_running(pid)) or status is not None:
            raise BadParameter(
                f"SkillsBrain already running on http://{current_host}:{current_port} "
                f"(pid={pid}). Use `skillsbrain status` or `skillsbrain stop`."
            )

    if is_port_open(host, port, timeout=0.5):
        status = probe_admin_status(host, port, timeout=0.5)
        if status and status.get("service") == SERVICE_NAME:
            raise BadParameter(
                f"SkillsBrain already running on http://{host}:{port} "
                f"(pid={status.get('pid', 'unknown')}). Use `skillsbrain status` or `skillsbrain stop`."
            )
        raise BadParameter(f"Port {port} is already in use. Use `skillsbrain status` or change --port.")


def format_runtime_status(runtime: dict[str, Any] | None, admin_status: dict[str, Any] | None, runtime_file: Path) -> list[str]:
    source = admin_status or runtime or {}
    if not source:
        return [
            "Status: stopped",
            f"Runtime file: {runtime_file}",
        ]

    pid = source.get("pid")
    host = source.get("host", DEFAULT_HOST)
    port = source.get("port", DEFAULT_PORT)
    status = source.get("status", "unknown")
    ready = source.get("ready")
    lifecycle = "running" if ready else status
    pid_alive = is_pid_running(pid) if isinstance(pid, int) else False

    return [
        f"Status: {lifecycle}",
        f"PID: {pid if pid is not None else 'unknown'} ({'alive' if pid_alive else 'not-alive'})",
        f"Address: http://{host}:{port}",
        f"Data dir: {source.get('data_dir', 'unknown')}",
        f"Skills dir: {source.get('skills_dir', 'unknown')}",
        f"Index dir: {source.get('index_dir', 'unknown')}",
        f"Log dir: {source.get('log_dir', 'unknown')}",
        f"Started at: {source.get('started_at', 'unknown')}",
        f"Ready at: {source.get('ready_at', 'not-ready')}",
        f"Runtime file: {runtime_file}",
    ]


def tail_text(path: Path, max_lines: int = 20) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max_lines:])


def resolve_probe_target(
    runtime: dict[str, Any] | None,
    host: str,
    port: int,
) -> tuple[str, int]:
    if runtime:
        return runtime.get("host", host), int(runtime.get("port", port))
    return host, port


@app.command()
def serve(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
    skills_dir: Path | None = typer.Option(None, "--skills", "-s", help="技能目录"),
    data_dir: Path | None = typer.Option(None, "--data-dir", "-d", help="数据根目录，默认 ~/.skillsbrain"),
    startup_timeout: float = typer.Option(STARTUP_TIMEOUT_SECONDS, "--startup-timeout", help="等待服务 ready 的超时时间（秒）"),
) -> None:
    """后台常驻启动 SkillsBrain，并阻塞到服务 ready。"""
    base_dir = resolve_base_dir(data_dir)
    ensure_not_running(base_dir, host, port)

    runtime_file = get_runtime_file(base_dir)
    shutdown_token = secrets.token_urlsafe(32)
    env = build_server_env(base_dir, skills_dir)
    env["SKILLSBRAIN_SHUTDOWN_TOKEN"] = shutdown_token

    log_dir = (base_dir / "logs").resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    service_log_file = log_dir / "skillsbrain-service.log"

    command = [
        sys.executable,
        "-m",
        "skillsbrain.cli",
        "run-server",
        "--host",
        host,
        "--port",
        str(port),
        "--data-dir",
        str(base_dir),
        "--runtime-file",
        str(runtime_file),
        "--shutdown-token",
        shutdown_token,
    ]
    if skills_dir:
        command.extend(["--skills", str(skills_dir.resolve())])

    creationflags = 0
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": env,
        "cwd": str(Path.cwd()),
        "close_fds": True,
    }
    if os.name == "nt":
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
        popen_kwargs["creationflags"] = creationflags
    else:
        popen_kwargs["start_new_session"] = True

    with service_log_file.open("ab") as log_fp:
        popen_kwargs["stdout"] = log_fp
        popen_kwargs["stderr"] = log_fp
        process = subprocess.Popen(command, **popen_kwargs)

    typer.echo(f"Starting {SERVICE_NAME} on http://{host}:{port}")
    try:
        status = wait_until_ready(host, port, timeout_seconds=startup_timeout, process=process)
    except RuntimeError as exc:
        log_tail = tail_text(service_log_file)
        typer.secho(f"Error: {exc}", fg="red")
        if log_tail:
            typer.echo("\nRecent service log:")
            typer.echo(log_tail)
        raise typer.Exit(1)

    typer.echo(
        f"{SERVICE_NAME} is ready on http://{host}:{port} "
        f"(pid={status.get('pid')}, data_dir={status.get('data_dir')})"
    )


@app.command(hidden=True, name="run-server")
def run_server(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
    skills_dir: Path | None = typer.Option(None, "--skills", "-s", help="技能目录"),
    data_dir: Path | None = typer.Option(None, "--data-dir", "-d", help="数据根目录"),
    runtime_file: Path = typer.Option(..., "--runtime-file", help="运行时文件路径"),
    shutdown_token: str = typer.Option(..., "--shutdown-token", help="关闭服务令牌"),
) -> None:
    """内部命令：以前台模式运行实际服务进程。"""
    import uvicorn

    base_dir = resolve_base_dir(data_dir)
    env = build_server_env(base_dir, skills_dir)
    os.environ.update(env)

    initial_runtime = {
        "service": SERVICE_NAME,
        "pid": os.getpid(),
        "host": host,
        "port": port,
        "data_dir": str(base_dir),
        "skills_dir": env["SKILLSBRAIN_SKILLS_DIR"],
        "index_dir": env["SKILLSBRAIN_INDEX_DIR"],
        "log_dir": env["SKILLSBRAIN_LOG_DIR"],
        "started_at": now_iso(),
        "ready_at": None,
        "status": "starting",
        "ready": False,
        "shutdown_token": shutdown_token,
    }
    write_runtime_file(runtime_file, initial_runtime)

    from skillsbrain.api.main import create_app

    app_instance = create_app(
        skills_dir=Path(env["SKILLSBRAIN_SKILLS_DIR"]),
        index_dir=Path(env["SKILLSBRAIN_INDEX_DIR"]),
        runtime_file=runtime_file,
        runtime_metadata=initial_runtime,
        shutdown_token=shutdown_token,
    )
    config = uvicorn.Config(app_instance, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    app_instance.state.server = server
    try:
        server.run()
    finally:
        remove_runtime_file(runtime_file)


@app.command()
def status(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
    data_dir: Path | None = typer.Option(None, "--data-dir", "-d", help="数据根目录，默认 ~/.skillsbrain"),
) -> None:
    """检查当前服务状态。"""
    base_dir = resolve_base_dir(data_dir)
    runtime_file, runtime = load_runtime(base_dir)
    cleanup_stale_runtime(runtime_file, runtime)
    runtime = read_runtime_file(runtime_file)
    probe_host, probe_port = resolve_probe_target(runtime, host, port)
    admin_status = probe_admin_status(probe_host, probe_port, timeout=1.0)
    if admin_status is None and (probe_host, probe_port) != (host, port):
        admin_status = probe_admin_status(host, port, timeout=1.0)

    if admin_status and admin_status.get("service") != SERVICE_NAME:
        admin_status = None

    for line in format_runtime_status(runtime, admin_status, runtime_file):
        typer.echo(line)


@app.command()
def stop(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
    data_dir: Path | None = typer.Option(None, "--data-dir", "-d", help="数据根目录，默认 ~/.skillsbrain"),
    timeout: float = typer.Option(STOP_TIMEOUT_SECONDS, "--timeout", help="等待服务关闭的超时时间（秒）"),
) -> None:
    """关闭当前 SkillsBrain 服务。"""
    base_dir = resolve_base_dir(data_dir)
    runtime_file, runtime = load_runtime(base_dir)
    cleanup_stale_runtime(runtime_file, runtime)
    runtime = read_runtime_file(runtime_file)
    probe_host, probe_port = resolve_probe_target(runtime, host, port)
    admin_status = probe_admin_status(probe_host, probe_port, timeout=1.0)
    if admin_status is None and (probe_host, probe_port) != (host, port):
        admin_status = probe_admin_status(host, port, timeout=1.0)

    active_runtime = admin_status or runtime
    if not active_runtime:
        typer.echo("SkillsBrain is not running.")
        return

    runtime_host = active_runtime.get("host", host)
    runtime_port = int(active_runtime.get("port", port))
    pid = active_runtime.get("pid")
    token = None
    if runtime:
        token = runtime.get("shutdown_token")

    if token:
        shutdown_url = f"{get_server_url(runtime_host, runtime_port)}/api/admin/shutdown"
        shutdown_resp = try_request_json("POST", shutdown_url, json={"token": token}, timeout=5)
        if shutdown_resp is not None:
            typer.echo(f"Stopping {SERVICE_NAME} on http://{runtime_host}:{runtime_port}")
            if isinstance(pid, int) and wait_for_pid_exit(pid, timeout):
                remove_runtime_file(runtime_file)
                typer.echo(f"{SERVICE_NAME} stopped.")
                return
            if not is_port_open(runtime_host, runtime_port, timeout=0.5):
                remove_runtime_file(runtime_file)
                typer.echo(f"{SERVICE_NAME} stopped.")
                return

    if isinstance(pid, int) and is_pid_running(pid):
        typer.echo(f"Graceful shutdown unavailable, terminating pid={pid}.")
        try:
            terminate_pid(pid)
        except OSError as exc:
            typer.secho(f"Error: Failed to terminate pid={pid}: {exc}", fg="red")
            raise typer.Exit(1)
        if wait_for_pid_exit(pid, timeout):
            remove_runtime_file(runtime_file)
            typer.echo(f"{SERVICE_NAME} stopped.")
            return
        typer.secho(f"Error: Timed out waiting for pid={pid} to exit.", fg="red")
        raise typer.Exit(1)

    remove_runtime_file(runtime_file)
    typer.echo("Removed stale runtime metadata.")


@app.command()
def match(
    query: str = typer.Argument(..., help="查询内容"),
    agent_type: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent 类型"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="会话 ID"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="返回数量"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
) -> None:
    """查询匹配的技能。"""
    url = f"{get_server_url(host, port)}/api/skill/match"

    skills = request_json(
        "POST",
        url,
        json={
            "query": query,
            "agent_type": agent_type,
            "session_id": session_id,
            "top_k": top_k,
        },
        timeout=10,
    )
    if not skills:
        typer.echo("No matching skills found.")
        return

    for skill in skills:
        typer.echo(f"\n{skill['name']} (score: {skill['score']:.4f})")
        typer.echo(f"  ID: {skill.get('skill_id', '')}")
        typer.echo(f"  Source: {skill.get('source_name', '')}")
        typer.echo(f"  {skill['description']}")
        typer.echo(f"  Tags: {', '.join(skill['tags'])}")


@app.command(name="list")
def list_skills_command(
    agent_type: Optional[str] = typer.Option(None, "--agent", "-a"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
) -> None:
    """列出所有技能。"""
    url = f"{get_server_url(host, port)}/api/skill/list"

    data = request_json(
        "GET",
        url,
        params={"agent_type": agent_type, "offset": 0, "limit": 200},
        timeout=10,
    )
    typer.echo(f"Total: {data['total']} skills (showing {len(data['skills'])})\n")

    for skill in data["skills"]:
        status_value = "ON" if skill.get("enabled", True) else "OFF"
        typer.echo(f"  [{status_value}] {skill['name']} ({skill.get('skill_id', '')}) [{skill.get('source_name', '')}]")


@app.command()
def stats(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
) -> None:
    """查看索引统计。"""
    url = f"{get_server_url(host, port)}/api/skill/stats"

    data = request_json("GET", url, timeout=10)
    typer.echo(f"Total skills: {data['total']}")
    typer.echo(f"Model: {data['model']}")


@app.command()
def reindex(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
) -> None:
    """重建索引。"""
    url = f"{get_server_url(host, port)}/api/skill/reindex"

    data = request_json("POST", url, timeout=30)
    typer.echo(f"Reindexed {data['indexed']} skills.")


@app.command()
def subscribe(
    path: Path = typer.Argument(..., help="要订阅的技能目录"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="订阅源名称"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
) -> None:
    """订阅一个外部 skills 目录。"""
    url = f"{get_server_url(host, port)}/api/source/subscribe"
    data = request_json("POST", url, json={"path": str(path), "name": name}, timeout=30)
    typer.echo(f"Subscribed: {data['name']} -> {data['root']} ({data['indexed']} skills)")


@app.command()
def unsubscribe(
    name_or_root: str = typer.Argument(..., help="订阅名或目录路径"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
) -> None:
    """取消订阅一个外部 skills 目录。"""
    url = f"{get_server_url(host, port)}/api/source/unsubscribe"
    data = request_json("POST", url, json={"name_or_root": name_or_root}, timeout=30)
    typer.echo(f"Unsubscribed: {data['name']} ({data['removed']} skills removed)")


@app.command()
def sources(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
) -> None:
    """列出已订阅源。"""
    url = f"{get_server_url(host, port)}/api/source/list"
    data = request_json("GET", url, timeout=10)
    if not data.get("sources"):
        typer.echo("No subscriptions.")
        return
    for item in data["sources"]:
        typer.echo(f"- {item['name']}: {item['root']} (enabled={item.get('enabled', True)})")


if __name__ == "__main__":
    app()
