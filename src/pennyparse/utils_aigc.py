import json
from ._client import ChatClient, ChatSession, response_message
from .utils import extract_md_codeblock, _extract_between
from .config import pp_config
from .logger import get_logger
logger = get_logger("utils_aigc")

def ai_chat_to_json_obj(client: ChatClient, session: ChatSession)->dict:
    for retry in range(int(pp_config.get("aigc.agent", {}).get("max_retry",3))):
        resp_payload = client.create(session)
        txt : str = response_message(resp_payload)[-1].get("content","")
        json_txt = extract_md_codeblock(txt) if "```" in txt else _extract_between(txt, "{", "}")
        try:
            return json.loads(json_txt)
        except Exception as e:
            logger.warning(f"ai_chat_to_json_obj retry {retry} failed, response: {txt}, reason:\n{e}")
            continue
    raise Exception("failed to get json from ai chat")
