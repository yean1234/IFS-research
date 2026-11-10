# compile-check — Unity 없이 C# 확인

Unity 에디터·배치모드를 쓸 수 없는 곳(CI, 이 저장소의 작업 환경)에서 `Assets/IFS`의 C#을 확인합니다. `Assets` 밖이라 Unity는 이 폴더를 컴파일하지 않습니다.

```bash
dotnet build IFS.SceneSpec.CompileCheck.csproj          # Runtime + Editor 스크립트 컴파일 (netstandard2.1, C# 9, 경고 = 오류)
dotnet test Tests/IFS.SceneSpec.CompileCheck.Tests.csproj   # Assets/IFS/Tests/Editor의 EditMode 테스트를 NUnit으로
```

| 무엇을 | 얼마나 확인되나 |
| --- | --- |
| `SceneSpecV2` · `SceneSpecJson` · `SceneParams` · `ExperimentRecorder` | 실제 Newtonsoft.Json 13.0.3으로 컴파일하고 테스트가 실행된다 |
| `SceneLoader` · `SpecMotion` · `InspectorPathSource` · Editor 메뉴 | `Stubs/UnityStubs.cs`(이름·시그니처만 흉내 낸 스텁)로 **타입 검사만** 한다. 동작은 Unity에서 확인해야 한다 |

스텁에 없는 Unity API를 새로 쓰면 빌드가 실패합니다. 그때는 실제 Unity API와 같은 시그니처로 스텁에 추가합니다.
