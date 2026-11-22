// Unity WebGL → 브라우저 알림(PreviewBridge.Notify). 외부 스크립트·네트워크를 쓰지 않는다.
// 페이지는 window.ifsPreviewOnMessage = function (kind, payload) { … } 를 두거나 'ifs-preview' 이벤트(detail = {kind, payload})를 듣는다.
// kind: ready · loaded · error · capture. payload는 JSON 객체(문자열을 여기서 파싱해 넘긴다).
mergeInto(LibraryManager.library, {
  IFSPreview_Notify: function (kindPtr, payloadPtr) {
    var kind = UTF8ToString(kindPtr);
    var text = UTF8ToString(payloadPtr);
    var payload;
    try { payload = JSON.parse(text); } catch (e) { payload = { parseError: String(e), raw: text }; }
    try {
      if (typeof window.ifsPreviewOnMessage === 'function') window.ifsPreviewOnMessage(kind, payload);
      window.dispatchEvent(new CustomEvent('ifs-preview', { detail: { kind: kind, payload: payload } }));
    } catch (e) {
      console.error('[IFSPreview] 알림 처리 중 오류', e);
    }
  }
});
