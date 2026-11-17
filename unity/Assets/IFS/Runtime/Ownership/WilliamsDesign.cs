// 제시 순서: 5조건 Williams 설계(라틴 방진 2개 = 10행). 각 조건이 각 위치에 2번, 바로 앞뒤 순서쌍(a→b)이 2번씩.
// 표는 상수다(난수 없음). 성질은 EditMode 테스트(OwnershipVariantTests)가 확인한다.
//   방진 1: 첫 행 0 1 4 2 3, 행 i = 첫 행 + i (mod 5). 방진 2: 방진 1의 각 행을 뒤집음.
//   조건 번호: 0 orig, 1 form, 2 color, 3 size, 4 motion.
namespace IFS.SceneSpec.Ownership
{
    public static class WilliamsDesign
    {
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

        /// <summary>참여자 번호(1 이상) → 행 번호 0–9.</summary>
        public static int RowFor(int participantNumber) => (participantNumber - 1) % Rows.Length;

        /// <summary>참여자 번호(1 이상) → 균형 비트 0/1.</summary>
        public static int CbFor(int participantNumber) => (participantNumber - 1) % 2;

        public static string[] OrderFor(int participantNumber)
        {
            var row = Rows[RowFor(participantNumber)];
            var order = new string[row.Length];
            for (int i = 0; i < row.Length; i++) order[i] = Conditions[row[i]];
            return order;
        }
    }
}
