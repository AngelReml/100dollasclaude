"""PLAN-v5 D21: the buttons webllm never presses, in the catalog's languages (extension/common.js, the same
rule the page driver applies to every click it makes)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

FORBIDDEN = [
    # publish / share / delete / regenerate / deploy / pay / log out / report
    "Publish", "Publicar", "Publier", "Veröffentlichen", "Pubblica", "发布", "發佈", "公開する", "공개",
    "Share", "Compartir enlace", "Partager", "Teilen", "Condividi", "分享", "共有", "공유",
    "Delete chat", "Borrar", "Eliminar conversación", "Supprimer", "Löschen", "删除", "削除", "삭제",
    "Regenerate response", "Regenerar", "Régénérer", "重新生成", "再生成", "Retry", "Reintentar",
    "Deploy", "Desplegar", "Déployer", "部署", "デプロイ", "배포",
    "Upgrade to Pro", "Subscribe", "Suscribirse", "Pagar", "Pay now", "Buy", "Comprar", "订阅", "升级",
    "Log out", "Sign out", "Cerrar sesión", "Déconnexion", "退出登录", "ログアウト", "Report", "Denunciar", "举报",
]
ALLOWED = [
    "Send message", "Enviar mensaje", "发送", "Copy", "Copiar", "复制", "Stop generating", "Detener",
    "Qwen3.8-Max", "GLM-5.2", "Modelo Pro", "Pensar", "Deep Research", "Investigación profunda", "Buscar en la web",
    "Subir archivo", "Adjuntar y más", "Crear imagen", "Web Dev", "深度思考", "联网搜索", "Paypal", "Payload",
]


def test_every_forbidden_button_in_every_language_and_nothing_else():
    js = ("const c=require('./extension/common.js');const t=" + json.dumps(FORBIDDEN + ALLOWED) +
          ";console.log(JSON.stringify(t.map(x=>c.FORBIDDEN_RE.test(x))))")
    out = json.loads(subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    got = dict(zip(FORBIDDEN + ALLOWED, out))
    assert [k for k in FORBIDDEN if not got[k]] == []
    assert [k for k in ALLOWED if got[k]] == []


def test_every_click_the_driver_makes_goes_through_the_rule():
    driver = (ROOT / "extension" / "driver.js").read_text("utf-8")
    # the only raw .click() calls: inside safeClick, and send/copy which check the same rule just before
    raw = [line.strip() for line in driver.splitlines() if ".click()" in line]
    assert sorted(raw) == sorted(["el.click();", "b.click();", "cps[cps.length - 1].click();"]), raw
    assert "if (b && !FORBIDDEN_RE_EARLY.test(nameOf(b)))" in driver
    assert 'if (FORBIDDEN_RE_EARLY.test(nameOf(cps[cps.length - 1]))) return { ok: false, error: "forbidden" };' in driver
