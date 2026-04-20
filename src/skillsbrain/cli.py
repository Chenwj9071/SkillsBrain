"""SkillsBrain CLI"""
import os
from pathlib import Path
from typing import Optional

import requests
import typer

app = typer.Typer(
    name="skillsbrain",
    help="Local skill routing engine for AI Agents",
    add_completion=False,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_SKILLS_DIR = Path.cwd() / "skills"


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
        typer.secho(f"Error: SkillsBrain returned HTTP {exc.response.status_code if exc.response else 'error'}.", fg="red")
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


@app.command()
def serve(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
    skills_dir: Path = typer.Option(None, "--skills", "-s", help="技能目录"),
):
    """启动 SkillsBrain 服务"""
    import uvicorn

    if skills_dir:
        os.environ["SKILLSBRAIN_SKILLS_DIR"] = str(skills_dir.resolve())

    from skillsbrain.api.main import create_app

    app = create_app()
    typer.echo(f"Starting SkillsBrain on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


@app.command()
def match(
    query: str = typer.Argument(..., help="查询内容"),
    agent_type: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent 类型"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="会话ID"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="返回数量"),
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """查询匹配的技能"""
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


@app.command()
def list(
    agent_type: Optional[str] = typer.Option(None, "--agent", "-a"),
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """列出所有技能"""
    url = f"{get_server_url(host, port)}/api/skill/list"

    data = request_json(
        "GET",
        url,
        params={"agent_type": agent_type, "offset": 0, "limit": 200},
        timeout=10,
    )
    typer.echo(f"Total: {data['total']} skills (showing {len(data['skills'])})\n")

    for skill in data["skills"]:
        status = "✓" if skill.get("enabled", True) else "✗"
        typer.echo(f"  [{status}] {skill['name']} ({skill.get('skill_id', '')}) [{skill.get('source_name', '')}]")


@app.command()
def stats(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """查看索引统计"""
    url = f"{get_server_url(host, port)}/api/skill/stats"

    data = request_json("GET", url, timeout=10)
    typer.echo(f"Total skills: {data['total']}")
    typer.echo(f"Model: {data['model']}")


@app.command()
def reindex(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """重建索引"""
    url = f"{get_server_url(host, port)}/api/skill/reindex"

    data = request_json("POST", url, timeout=30)
    typer.echo(f"Reindexed {data['indexed']} skills.")


@app.command()
def subscribe(
    path: Path = typer.Argument(..., help="要订阅的技能目录"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="订阅源名称"),
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """订阅一个外部 skills 目录"""
    url = f"{get_server_url(host, port)}/api/source/subscribe"
    data = request_json("POST", url, json={"path": str(path), "name": name}, timeout=30)
    typer.echo(f"Subscribed: {data['name']} -> {data['root']} ({data['indexed']} skills)")


@app.command()
def unsubscribe(
    name_or_root: str = typer.Argument(..., help="订阅名或目录路径"),
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """取消订阅一个外部 skills 目录"""
    url = f"{get_server_url(host, port)}/api/source/unsubscribe"
    data = request_json("POST", url, json={"name_or_root": name_or_root}, timeout=30)
    typer.echo(f"Unsubscribed: {data['name']} ({data['removed']} skills removed)")


@app.command()
def sources(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """列出已订阅源"""
    url = f"{get_server_url(host, port)}/api/source/list"
    data = request_json("GET", url, timeout=10)
    if not data.get("sources"):
        typer.echo("No subscriptions.")
        return
    for item in data["sources"]:
        typer.echo(f"- {item['name']}: {item['root']} (enabled={item.get('enabled', True)})")


if __name__ == "__main__":
    app()
