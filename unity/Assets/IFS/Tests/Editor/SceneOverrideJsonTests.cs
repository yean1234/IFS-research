// 덮어쓰기 목록 JSON(SceneOverrideJson)과 미리보기 배경 이름(PreviewBridge.ParseBackground). dotnet·Unity 둘 다에서 돈다.
using System;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class SceneOverrideJsonTests
    {
        [Test]
        public void Flat_object_splits_numbers_categories_and_shape_model()
        {
            var o = SceneOverrideJson.Parse("{\"material.brightness\":0.7,\"layout.size\":1,\"form.type\":\"blob\",\"motion.type\":\"still\",\"shapeModel\":\"Cube\"}", out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(o.Numbers["material.brightness"], Is.EqualTo(0.7));
            Assert.That(o.Numbers["layout.size"], Is.EqualTo(1.0));
            Assert.That(o.Categories["form.type"], Is.EqualTo("blob"));
            Assert.That(o.Categories["motion.type"], Is.EqualTo("still"));
            Assert.That(o.ShapeModel, Is.EqualTo("Cube"));
        }

        [TestCase("")]
        [TestCase("   ")]
        [TestCase("{}")]
        public void Empty_input_means_no_overrides(string json)
        {
            var o = SceneOverrideJson.Parse(json, out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(o, Is.Not.Null);
            Assert.That(o.IsEmpty, Is.True);
        }

        [TestCase("{\"material.brightness\":", "JSON을 읽지 못함")]
        [TestCase("[1,2]", "JSON 객체여야 함")]
        [TestCase("{\"a\":1} {\"b\":2}", "JSON을 읽지 못함")]
        [TestCase("{\"material.unknown\":0.5}", "수치 키가 아님")]
        [TestCase("{\"form.size\":\"big\"}", "범주 키가 아님")]
        [TestCase("{\"material.opacity\":1.5}", "0–1 밖")]
        [TestCase("{\"material.opacity\":-0.1}", "0–1 밖")]
        [TestCase("{\"form.type\":\"cloud\"}", "모르는 형태")]
        [TestCase("{\"motion.type\":\"dancing\"}", "모르는 motion.type")]
        [TestCase("{\"material.opacity\":null}", "숫자나 문자열이어야 함")]
        [TestCase("{\"material.opacity\":true}", "숫자나 문자열이어야 함")]
        [TestCase("{\"shapeModel\":3}", "문자열이어야 함")]
        [TestCase("{\"shapeModel\":\"Torus\"}", "모르는 모양 모형")]
        public void Invalid_input_is_rejected_with_a_reason(string json, string reason)
        {
            var o = SceneOverrideJson.Parse(json, out var errors);
            Assert.That(o, Is.Null);
            Assert.That(errors, Has.Some.Contains(reason));
        }

        [Test]
        public void Round_trips_the_manifest_overrides_format()
        {
            var a = new SceneOverride();
            a.Numbers["material.opacity"] = 0.25;
            a.Categories["form.type"] = "mist";
            var b = SceneOverrideJson.Parse(a.OverridesJson().ToString(), out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(b.ToString(), Is.EqualTo(a.ToString()));
        }

        [Test]
        public void Same_text_gives_the_same_override()
        {
            const string json = "{\"material.color.h\":0.3,\"form.posture\":\"curled\"}";
            var a = SceneOverrideJson.Parse(json, out var ea);
            var b = SceneOverrideJson.Parse(json, out var eb);
            Assert.That(ea, Is.EqualTo(eb));
            Assert.That(a?.ToString(), Is.EqualTo(b?.ToString()));
        }

        [TestCase(null, PreviewBackground.Scene)]
        [TestCase("scene", PreviewBackground.Scene)]
        [TestCase("Black", PreviewBackground.Black)]
        [TestCase("WHITE", PreviewBackground.White)]
        public void Background_names(string name, PreviewBackground expected) =>
            Assert.That(PreviewBridge.ParseBackground(name), Is.EqualTo(expected));

        [Test]
        public void Unknown_background_is_an_error() =>
            Assert.Throws<ArgumentException>(() => PreviewBridge.ParseBackground("grey"));
    }
}
