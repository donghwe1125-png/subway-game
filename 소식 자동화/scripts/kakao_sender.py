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
    # 함께 준다. 코드가 GitHub Secret을 대신 바꿔줄 수는 없으니, 새 값을 로그로
    # 크게 알려서 사용자가 직접 갱신할 기회를 준다.
    new_refresh_token = payload.get("refresh_token")
    if new_refresh_token:
        print(
            "⚠️ 카카오 refresh token이 갱신되었습니다 - GitHub Secrets의 "
            f"KAKAO_REFRESH_TOKEN을 새 값으로 업데이트해주세요: {new_refresh_token}",
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
