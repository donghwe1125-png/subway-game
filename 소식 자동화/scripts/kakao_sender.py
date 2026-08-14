import json
import sys

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
    payload = response.json()

    # 카카오는 refresh token 만료(약 60일)가 가까워지면 응답에 새 refresh token을
    # 함께 준다. 코드가 GitHub Secret을 대신 바꿔줄 수는 없으니 사용자에게 알려야
    # 하지만, 이 저장소는 public이라 Actions 로그도 전세계에 공개된다. 전체 값을
    # 찍으면 토큰이 그대로 유출되므로 마지막 6자리만 보여주고, 나머지는 사용자가
    # Task 11의 인가 코드 로그인 절차를 다시 진행해 직접 발급받도록 안내한다.
    new_refresh_token = payload.get("refresh_token")
    if new_refresh_token:
        token_suffix = new_refresh_token[-6:]
        print(
            f"⚠️ 카카오 refresh token이 갱신되었습니다 (...{token_suffix}). GitHub "
            "Secrets의 KAKAO_REFRESH_TOKEN을 업데이트해야 합니다 - 보안을 위해 "
            "전체 값은 로그에 남기지 않으니, Task 11의 카카오 인가 코드 로그인 "
            "절차를 다시 진행해 본인 계정에서 직접 새 refresh_token을 "
            "발급받아주세요.",
            file=sys.stderr,
        )

    return payload["access_token"]


def send_message(access_token: str, text: str) -> None:
    # 길이를 잘라내지 않는다. 분할은 message_formatter가 MAX_CHARS 기준으로 끝내며,
    # 그래도 너무 길면 카카오가 HTTP 오류로 크게 알려주는 편이 조용히 소식을
    # 잃는 것보다 낫다.
    template = {
        "object_type": "text",
        "text": text,
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
