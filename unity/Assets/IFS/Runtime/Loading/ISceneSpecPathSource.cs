// SceneSpec JSON 경로를 SceneLoader에 넘기는 쪽의 약속.
//
// 지금 있는 구현: InspectorPathSource (Inspector에 경로를 직접 입력).
// 자리만 둔 구현: 로컬 HTTP — 파이썬 면담 서버가 확정 직후 경로를 보내면 Unity가 로드한다.
//   예정 계약(구현하지 않음):
//     · Unity가 127.0.0.1의 포트 하나에서 POST /scene {"path": "<scenes/{sessionId}.json 절대 경로>"}를 받는다.
//       또는 Unity가 GET http://127.0.0.1:8000/api/sessions/{id}/scene 을 물어 path를 얻는다(서버에 이미 있음).
//     · 받은 경로는 메인 스레드에서 SpecPathChanged로 알린다(HttpListener 콜백 스레드에서 Unity API를 부르지 않는다).
//     · 외부 전송 없음: 127.0.0.1만 연다(AGENTS.md 5).
using System;

namespace IFS.SceneSpec
{
    public interface ISceneSpecPathSource
    {
        /// <summary>지금 로드할 SceneSpec JSON 경로. 없으면 false.</summary>
        bool TryGetSpecPath(out string path);

        /// <summary>새 경로가 들어왔을 때(HTTP 등 비동기 전달). 반드시 Unity 메인 스레드에서 발생시킨다.</summary>
        event Action<string> SpecPathChanged;
    }
}
