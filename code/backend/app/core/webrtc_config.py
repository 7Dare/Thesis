import os
from typing import Dict, List


def _split_csv(raw: str) -> List[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def get_webrtc_config() -> Dict:
    stun_urls = _split_csv(os.getenv("WEBRTC_STUN_URLS", "stun:stun.l.google.com:19302"))
    turn_urls = _split_csv(os.getenv("WEBRTC_TURN_URLS", ""))
    turn_username = os.getenv("WEBRTC_TURN_USERNAME", "")
    turn_credential = os.getenv("WEBRTC_TURN_CREDENTIAL", "")

    ice_servers = []
    if stun_urls:
        ice_servers.append({"urls": stun_urls if len(stun_urls) > 1 else stun_urls[0]})
    if turn_urls:
        turn = {"urls": turn_urls if len(turn_urls) > 1 else turn_urls[0]}
        if turn_username:
            turn["username"] = turn_username
        if turn_credential:
            turn["credential"] = turn_credential
        ice_servers.append(turn)

    return {
        "iceServers": ice_servers,
        "defaults": {
            "audioMutedOnJoin": True,
            "meshRoomLimit": 6,
        },
    }
