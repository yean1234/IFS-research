// 기본 형상(form.base, SceneSpec 2.2.0 — 결정 G21·G30, docs/asset-plan.md)의 닫힌 목록과 변형값 표.
// 스키마 shared/schemas/scene-spec.v2.2.json(form.base enum, $defs.baseVariant)과 같아야 한다(pytest가 C# 원문과 대조).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;

namespace IFS.SceneSpec
{
    public static class BaseShapes
    {
        public const string Key = "form.base";
        public const string VariantKey = "form.baseVariant";
        /// <summary>기본 형상을 그리지 않음(SceneParams의 form.base 기본값·덮어쓰기 값).</summary>
        public const string None = "none";

        public const string Container = "container";
        public const string Line = "line";
        public const string Sheet = "sheet";
        public const string Flame = "flame";
        public const string Drop = "drop";

        /// <summary>승인된 첫 묶음 5개(G30). 순서 = 만든 순서.</summary>
        public static readonly string[] All = { Container, Line, Sheet, Flame, Drop };

        /// <summary>기본 형상 → 쓰는 변형 키 → 허용 값(첫 값이 형상 프리셋 기본값).</summary>
        public static readonly IReadOnlyDictionary<string, IReadOnlyDictionary<string, string[]>> Variants =
            new Dictionary<string, IReadOnlyDictionary<string, string[]>>(StringComparer.Ordinal)
            {
                { Container, new Dictionary<string, string[]>(StringComparer.Ordinal) { { "opening", new[] { "wide", "narrow" } }, { "profile", new[] { "round", "square" } } } },
                { Line, new Dictionary<string, string[]>(StringComparer.Ordinal) { { "form", new[] { "curve", "tangle", "knot" } }, { "gauge", new[] { "normal", "thin", "thick" } } } },
                { Sheet, new Dictionary<string, string[]>(StringComparer.Ordinal) { { "drape", new[] { "paper", "cloth" } } } },
                { Flame, new Dictionary<string, string[]>(StringComparer.Ordinal) },
                { Drop, new Dictionary<string, string[]>(StringComparer.Ordinal) },
            };

        public static bool IsBase(string v) => v != null && Array.IndexOf(All, v) >= 0;

        /// <summary>기본 형상을 그릴 수 있는 form.type: blob(말하지 않아 기본값 blob인 경우 포함). docs/asset-plan.md 2-5절.</summary>
        public static bool FormAllowsBase(string formType) => formType == "blob";

        /// <summary>spec 변형값 → 이 기본 형상의 변형값 전체(정하지 않은 키는 기본값으로 채움). defaultsUsed에 채운 키(예: "gauge").
        /// 다른 기본 형상의 키(예: container에 drape)나 표에 없는 값은 쓰지 않고 problems에 남긴다.</summary>
        public static SortedDictionary<string, string> Resolve(string shape, BaseVariantSpec spec, List<string> defaultsUsed, List<string> problems)
        {
            var r = new SortedDictionary<string, string>(StringComparer.Ordinal);
            if (!IsBase(shape)) return r;
            var table = Variants[shape];
            var given = new Dictionary<string, string>(StringComparer.Ordinal);
            if (spec != null) foreach (var kv in spec.Pairs()) given[kv.Key] = kv.Value;
            foreach (var kv in given)
                if (!table.ContainsKey(kv.Key)) problems?.Add($"form.baseVariant.{kv.Key}: {shape}에는 없는 변형 키(무시)");
            foreach (var kv in table)
            {
                if (given.TryGetValue(kv.Key, out var v) && Array.IndexOf(kv.Value, v) >= 0) r[kv.Key] = v;
                else
                {
                    if (given.ContainsKey(kv.Key)) problems?.Add($"form.baseVariant.{kv.Key}: {v}는 {shape}의 값이 아님(기본값으로 그림)");
                    r[kv.Key] = kv.Value[0];
                    defaultsUsed?.Add(kv.Key);
                }
            }
            return r;
        }
    }
}
