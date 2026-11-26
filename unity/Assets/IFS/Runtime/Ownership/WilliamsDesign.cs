// 제시 순서: Williams 설계. 표는 상수·규칙으로 정한다(난수 없음). 성질은 EditMode 테스트(OwnershipVariantTests)가 확인한다.
//   일반 규칙(n조건): 첫 행 0 1 n−1 2 n−2 3 …, 행 i = 첫 행 + i (mod n).
//     n 짝수 → 이 방진 n행. n 홀수 → 방진 2개 = 2n행(방진 2 = 방진 1의 각 행을 뒤집음).
//     한 주기(전체 행)에서 각 조건이 각 위치에 같은 횟수, 바로 앞뒤 순서쌍(a→b)도 같은 횟수(짝수 1번, 홀수 2번).
//   5조건: 아래 Rows 표(10행) 그대로 — 일반 규칙과 같은 표이고, 0.2 이전 세션을 그대로 재현하려고 상수로 둔다.
//     조건 번호: 0 orig, 1 form, 2 color, 3 size, 4 motion.
//   조건 목록은 생성기가 실제로 보여 줄 것(orig + 어긋난 변형 + 유효한 같은 말·다른 값 쌍)을 먼저 정한 뒤 넘긴다.
//   행 = (참여자 번호 − 1) mod 행 수.
// 균형 비트(cb, 어긋난 변형의 방향)는 행과 따로 돌도록 행 수 단위마다 뒤집는다: cb = ((번호 − 1) mod 2) XOR (⌊(번호 − 1) / 행 수⌋ mod 2).
//   5조건(10행)은 X31 규칙과 같다. 홀수 n이면 행 수 2n이 짝수라 2 × 행 수 명이면 행 × cb 칸이 한 번씩 찬다.
using System;
using System.Collections.Generic;

namespace IFS.SceneSpec.Ownership
{
    public static class WilliamsDesign
    {
        /// <summary>한 세션의 최대 조건 수. 실험자 키가 한 자리(1–9)라 마지막 선택에서 이보다 많으면 번호를 받을 수 없다.</summary>
        public const int MaxConditions = 9;

        public static readonly string[] Conditions = { "orig", "form", "color", "size", "motion" };

        public static readonly int[][] Rows =
        {
            new[] { 0, 1, 4, 2, 3 },
            new[] { 1, 2, 0, 3, 4 },
            new[] { 2, 3, 1, 4, 0 },
            new[] { 3, 4, 2, 0, 1 },
            new[] { 4, 0, 3, 1, 2 },
            new[] { 3, 2, 4, 1, 0 },
            new[] { 4, 3, 0, 2, 1 },
            new[] { 0, 4, 1, 3, 2 },
            new[] { 1, 0, 2, 4, 3 },
            new[] { 2, 1, 3, 0, 4 },
        };

        /// <summary>n조건 Williams 표. n = 5는 Rows(상수 표)를 돌려준다.</summary>
        public static int[][] RowsFor(int n)
        {
            if (n < 1) throw new ArgumentOutOfRangeException(nameof(n), "조건 수는 1 이상");
            if (n == 5) return Rows;
            return Generate(n);
        }

        /// <summary>일반 규칙으로 만든 표(n = 5도 규칙대로). 테스트가 Rows와 같은지 확인한다.</summary>
        public static int[][] Generate(int n)
        {
            if (n < 1) throw new ArgumentOutOfRangeException(nameof(n), "조건 수는 1 이상");
            var first = new int[n];
            int lo = 1, hi = n - 1;
            for (int k = 1; k < n; k++) first[k] = k % 2 == 1 ? lo++ : hi--;
            var rows = new List<int[]>();
            for (int i = 0; i < n; i++)
            {
                var r = new int[n];
                for (int k = 0; k < n; k++) r[k] = (first[k] + i) % n;
                rows.Add(r);
            }
            if (n % 2 == 1)
                for (int i = 0; i < n; i++)
                {
                    var r = (int[])rows[i].Clone();
                    Array.Reverse(r);
                    rows.Add(r);
                }
            return rows.ToArray();
        }

        /// <summary>참여자 번호(1 이상) → 5조건 표의 행 번호 0–9.</summary>
        public static int RowFor(int participantNumber) => (participantNumber - 1) % Rows.Length;

        /// <summary>참여자 번호(1 이상) → n조건 표의 행 번호.</summary>
        public static int RowFor(int participantNumber, int n) => (participantNumber - 1) % RowsFor(n).Length;

        /// <summary>
        /// 참여자 번호(1 이상) → 균형 비트 0/1. 1–10번은 (번호 − 1) mod 2, 11–20번은 그 반대(10명 단위마다 뒤집음).
        /// 그래서 10명 단위 안에서 cb가 5:5이고, 20명이면 순서 행(10) × cb(2) 20칸이 한 번씩 채워진다
        /// (행 번호와 cb가 늘 같은 홀짝으로 묶이지 않는다).
        /// </summary>
        public static int CbFor(int participantNumber) => CbFor(participantNumber, Conditions.Length);

        /// <summary>n조건: cb = ((번호 − 1) mod 2) XOR (⌊(번호 − 1) / 행 수(n)⌋ mod 2). n = 5는 CbFor(번호)와 같다.</summary>
        public static int CbFor(int participantNumber, int n) =>
            ((participantNumber - 1) % 2) ^ (((participantNumber - 1) / RowsFor(n).Length) % 2);

        /// <summary>5조건(orig, form, color, size, motion) 순서.</summary>
        public static string[] OrderFor(int participantNumber) => OrderFor(participantNumber, Conditions);

        /// <summary>조건 목록(번호 = 목록 위치) → 이 참여자의 제시 순서.</summary>
        public static string[] OrderFor(int participantNumber, IReadOnlyList<string> conditions)
        {
            var row = RowsFor(conditions.Count)[RowFor(participantNumber, conditions.Count)];
            var order = new string[row.Length];
            for (int i = 0; i < row.Length; i++) order[i] = conditions[row[i]];
            return order;
        }
    }
}
