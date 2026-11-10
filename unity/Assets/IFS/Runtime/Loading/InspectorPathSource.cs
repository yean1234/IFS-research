// 경로 전달 방식 1: Inspector에 SceneSpec JSON 경로를 직접 넣는다.
using System;
using UnityEngine;

namespace IFS.SceneSpec
{
    [AddComponentMenu("IFS/SceneSpec Path (Inspector)")]
    public sealed class InspectorPathSource : MonoBehaviour, ISceneSpecPathSource
    {
        [Tooltip("SceneSpec v2 JSON 경로. 상대 경로는 StreamingAssets 기준(예: IFS/examples/EX01.json). " +
                 "챗봇 출력은 절대 경로로(…/chatbot/logs/scenes/P07.json).")]
        [SerializeField] string specPath = "";

        public string SpecPath
        {
            get => specPath;
            set => specPath = value;
        }

#pragma warning disable 0067 // Inspector 방식은 경로가 바뀌어도 알리지 않는다(SceneLoader의 '다시 불러오기'를 쓴다)
        public event Action<string> SpecPathChanged;
#pragma warning restore 0067

        public bool TryGetSpecPath(out string path)
        {
            path = specPath;
            return !string.IsNullOrWhiteSpace(specPath);
        }
    }
}
