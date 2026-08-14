import json

import requests

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def refresh_access_token(rest_api_key: str, refresh_token: str) -> str:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def send_message(access_token: str, text: str) -> None:
    template = {
        "object_type": "text",
        "text": text[:1000],
        "link": {"web_url": "https://cba.snu.ac.kr/newsroom/notice?sc=y"},
        "button_title": "바로가기",
    }
    response = requests.post(
        SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=10,
    )
    response.raise_for_status()
