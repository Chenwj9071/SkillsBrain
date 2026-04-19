"""SkillsBrain CLI"""
import os
import sys
from pathlib import Path
from typing import Optional

import typer
import requests

app = typer.Typer(
    name="skillsbrain",
    help="Local skill routing engine for AI Agents",
    add_completion=False,
)

# 默认配置
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_SKILLS_DIR = Path.cwd() / "skills"


def get_server_url(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    return f"http://{host}:{port}"


@app.command()
def serve(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help="服务地址"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="服务端口"),
    skills_dir: Path = typer.Option(None, "--skills", "-s", help="技能目录"),
):
    """启动 SkillsBrain 服务"""
    import uvicorn
    
    # 设置技能目录
    if skills_dir:
        os.environ["SKILLSBRAIN_SKILLS_DIR"] = str(skills_dir.resolve())
    
    # 延迟导入，确保环境变量生效
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
    
    try:
        r = requests.post(
            url,
            json={
                "query": query,
                "agent_type": agent_type,
                "session_id": session_id,
                "top_k": top_k,
            },
            timeout=10,
        )
        r.raise_for_status()
        
        skills = r.json()
        if not skills:
            typer.echo("No matching skills found.")
            return
        
        for skill in skills:
            typer.echo(f"\n{skill['name']} (score: {skill['score']:.4f})")
            typer.echo(f"  {skill['description']}")
            typer.echo(f"  Tags: {', '.join(skill['tags'])}")
            
    except requests.exceptions.ConnectionError:
        typer.secho("Error: Cannot connect to SkillsBrain server.", fg="red")
        typer.echo(f"Make sure the server is running: skillsbrain serve --port {port}")
        raise typer.Exit(1)


@app.command()
def list(
    agent_type: Optional[str] = typer.Option(None, "--agent", "-a"),
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """列出所有技能"""
    url = f"{get_server_url(host, port)}/api/skill/list"
    
    try:
        r = requests.get(url, params={"agent_type": agent_type}, timeout=10)
        r.raise_for_status()
        
        data = r.json()
        typer.echo(f"Total: {data['total']} skills\n")
        
        for skill in data["skills"]:
            status = "✓" if skill.get("enabled", "true").lower() == "true" else "✗"
            typer.echo(f"  [{status}] {skill['name']}")
            
    except requests.exceptions.ConnectionError:
        typer.secho("Error: Cannot connect to SkillsBrain server.", fg="red")
        raise typer.Exit(1)


@app.command()
def stats(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """查看索引统计"""
    url = f"{get_server_url(host, port)}/api/skill/stats"
    
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        
        data = r.json()
        typer.echo(f"Total skills: {data['total']}")
        typer.echo(f"Model: {data['model']}")
        
    except requests.exceptions.ConnectionError:
        typer.secho("Error: Cannot connect to SkillsBrain server.", fg="red")
        raise typer.Exit(1)


@app.command()
def reindex(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p"),
):
    """重建索引"""
    url = f"{get_server_url(host, port)}/api/skill/reindex"
    
    try:
        r = requests.post(url, timeout=30)
        r.raise_for_status()
        
        data = r.json()
        typer.echo(f"Reindexed {data['indexed']} skills.")
        
    except requests.exceptions.ConnectionError:
        typer.secho("Error: Cannot connect to SkillsBrain server.", fg="red")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
