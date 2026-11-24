# -*- coding: utf-8 -*-
"""推送模块：Server酱(微信) / SMTP邮件 / Telegram / 企业微信 / 钉钉。
按 config.yaml 中 push.channels 配置启用，可多选。"""
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import requests


def push_all(cfg, subject, text, html=None):
    """按配置依次推送，返回 [(channel, ok, msg)]。"""
    results = []
    channels = (cfg.get("push") or {}).get("channels") or []
    for ch in channels:
        name = ch.get("type")
        try:
            if name == "serverchan":
                _serverchan(ch, subject, text)
            elif name == "email":
                _email(ch, subject, text, html)
            elif name == "telegram":
                _telegram(ch, text)
            elif name == "wecom_webhook":
                _wecom(ch, text)
            elif name == "dingtalk_webhook":
                _dingtalk(ch, text)
            else:
                raise ValueError(f"未知推送渠道: {name}")
            results.append((name, True, "ok"))
        except Exception as e:
            results.append((name, False, str(e)))
    return results


def _serverchan(ch, subject, text):
    # Server酱3.0: https://sct.ftqq.com ，SendKey 填到配置里
    r = requests.post(
        f"https://sctapi.ftqq.com/{ch['sendkey']}.send",
        data={"title": subject[:32], "desp": text}, timeout=20)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError("ServerChan返回异常: {}".format(j))


def _email(ch, subject, text, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((Header("财经早报", "utf-8").encode(), ch["from"]))
    msg["To"] = ch["to"]
    msg.attach(MIMEText(text, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    if ch.get("ssl", True):
        server = smtplib.SMTP_SSL(ch["host"], ch.get("port", 465),
                                  timeout=20, context=ctx)
    else:
        server = smtplib.SMTP(ch["host"], ch.get("port", 25), timeout=20)
        server.starttls(context=ctx)
    try:
        server.login(ch["user"], ch["password"])
        server.sendmail(ch["from"], [ch["to"]], msg.as_string())
    finally:
        server.quit()


def _telegram(ch, text):
    # 4096 字符上限，超长分段
    url = f"https://api.telegram.org/bot{ch['bot_token']}/sendMessage"
    for i in range(0, len(text), 3800):
        requests.post(url, json={
            "chat_id": ch["chat_id"], "text": text[i:i + 3800],
        }, timeout=20).raise_for_status()


def _wecom(ch, text):
    # 企业微信群机器人 webhook，markdown 消息 4096 上限
    requests.post(ch["webhook"], json={
        "msgtype": "markdown",
        "markdown": {"content": text[:4000]},
    }, timeout=20).raise_for_status()


def _dingtalk(ch, text):
    requests.post(ch["webhook"], json={
        "msgtype": "text",
        "text": {"content": text[:4500]},
    }, timeout=20).raise_for_status()
