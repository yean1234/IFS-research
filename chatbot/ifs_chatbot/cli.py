"""터미널 면담 데모.

  python -m ifs_chatbot.cli                       조건 2(챗봇), config/default.toml
  python -m ifs_chatbot.cli --condition static    조건 1(정적 프롬프트)
  python -m ifs_chatbot.cli --backend offline     LLM 없이
  python -m ifs_chatbot.cli --debug               매 턴 검증 결과(보이지 않은 턴 포함) 출력

명령: /넘어가기  /그만  /계속  /확인  /고침  /로그
"""
from __future__ import annotations

import argparse
import sys

from .config import load_config
from .controller import Runtime, SessionError

COMMANDS = {"/넘어가기": "skip", "/그만": "stop", "/계속": "continue", "/확인": "confirm"}


def _print_new(session, shown: int, debug: bool) -> int:
    for m in session.messages[shown:]:
        if m["speaker"] == "participant":
            continue
        tag = {"check": "확인", "crisis": "안내", "closing": "끝", "confirm": "확인", "info": "안내"}.get(m.get("kind"), "질문")
        print(f"\n[{tag}] {m['text']}")
        if debug and m.get("i") is not None:
            turn = session.log.turns[m["i"]]
            src = turn.get("source")
            print(f"   └ {src}" + (f" · 문구 {turn.get('phraseStatus')}" if turn.get("phraseStatus") else ""))
            for a in turn.get("attempts", []):
                state = "통과" if a["passed"] else "차단"
                utt = (a.get("parsed") or {}).get("utterance") or a.get("raw", "")[:60]
                print(f"     · 시도 {a['attempt'] + 1} {state}: {utt}" + ("" if a["passed"] else f"  ← {' / '.join(a.get('reasonsText') or a['reasons'])}"))
    return len(session.messages)


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.cli", description="IFS 심상화 면담 (터미널)")
    ap.add_argument("--config", help="config 이름(default|pilot) 또는 .toml 경로")
    ap.add_argument("--condition", choices=["chatbot", "static"])
    ap.add_argument("--backend", choices=["ollama", "offline"])
    ap.add_argument("--model")
    ap.add_argument("--session-id")
    ap.add_argument("--no-guard-model", action="store_true")
    ap.add_argument("--debug", action="store_true", help="검증 결과와 차단된 시도를 함께 보여 준다")
    args = ap.parse_args(argv)

    cfg = load_config(args.config).with_overrides(**{
        "llm.backend": args.backend, "llm.model": args.model,
        "guard.model_backend": "none" if args.no_guard_model else None,
    })
    rt = Runtime(cfg)
    for w in rt.warnings:
        print(f"! {w}")
    try:
        s = rt.new_session(args.condition or cfg.interview.condition, args.session_id)
    except SessionError as exc:
        print(f"세션을 시작할 수 없습니다: {exc}")
        sys.exit(1)
    print(f"세션 {s.id} · {s.view()['condition']['label']} · 로그: {s.log.path}")
    shown = _print_new(s, 0, args.debug)

    while s.awaiting != "none":
        try:
            if s.awaiting == "start":
                input("\n(Enter를 누르면 시작합니다) ")
                s.start()
            elif s.awaiting == "reply":
                text = input("\n> ").strip()
                if text in COMMANDS:
                    s.act(COMMANDS[text])
                elif text == "/로그":
                    for t in s.log.turns:
                        print(f"  #{t['i']} {t['speaker']:11} {t.get('source', ''):22} {t.get('text', '')[:50]}")
                    continue
                elif text:
                    s.reply(text)
                else:
                    continue
            elif s.awaiting == "soft_check":
                text = input("\n[계속] 또는 [그만] > ").strip()
                s.act("stop" if text in ("그만", "/그만") else "continue")
            elif s.awaiting == "confirm":
                print("\n--- 확정 텍스트 ---\n" + (s.confirm_draft or "") + "\n------------------")
                text = input("[이대로 맞아요]는 Enter, 고치려면 /고침 > ").strip()
                if text == "/고침":
                    print("고친 텍스트를 입력하세요. 빈 줄에서 끝납니다.")
                    lines = []
                    while True:
                        line = input()
                        if not line.strip():
                            break
                        lines.append(line)
                    s.act("edit", "\n".join(lines))
                else:
                    s.act("confirm")
        except SessionError as exc:
            print(f"! {exc}")
        except (KeyboardInterrupt, EOFError):
            print("\n중단합니다.")
            s.act("stop")
        shown = _print_new(s, shown, args.debug)

    print(f"\n세션 종료: {s.log.data.get('endedBy')} · 로그 {s.log.path}")
    if s.log.data.get("extraction"):
        ex = s.log.data["extraction"]
        print("추출 미리보기:", ", ".join(f"{a['_provenance']['trigger']}→{a['category']}" for a in ex["attributes"][:12]))
        print("사전 밖 내용어:", ", ".join(u["surface"] for u in ex["unmatched"]) or "없음")


if __name__ == "__main__":
    main()
