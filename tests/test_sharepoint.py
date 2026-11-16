import httpx

from ferrero.sync.sources import GRAPH, SharePointSource

DELTA = f"{GRAPH}/drives/drive-1/root/delta"


def graph(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if request.url.host == "login.microsoftonline.com":
        assert b"grant_type=client_credentials" in request.content
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    if request.url.host == "files.example.net":  # the pre-authenticated download URL
        assert "authorization" not in request.headers  # the Graph token must not leak to the redirect target
        return httpx.Response(200, content=b"%PDF-bytes")
    assert request.headers["authorization"] == "Bearer tok"
    if url == f"{GRAPH}/sites/contoso.sharepoint.com:/sites/Legal":
        return httpx.Response(200, json={"id": "site-1"})
    if url == f"{GRAPH}/sites/site-1/drives":
        return httpx.Response(200, json={"value": [
            {"id": "drive-0", "name": "Documents", "webUrl": "https://contoso.sharepoint.com/sites/Legal/Shared%20Documents"},
            {"id": "drive-1", "name": "Cases", "webUrl": "https://contoso.sharepoint.com/sites/Legal/Cases"}]})
    if url == DELTA:
        return httpx.Response(200, json={"@odata.nextLink": f"{DELTA}?token=2", "value": [
            {"id": "folder-1", "name": "TM-2024-428", "folder": {}, "parentReference": {"path": "/drives/drive-1/root:/UAE"}},
            {"id": "item-1", "name": "TM-2024-428_Judgment_EN.pdf", "file": {}, "cTag": "c1",
             "lastModifiedDateTime": "2026-11-01T08:00:00Z",
             "parentReference": {"path": "/drives/drive-1/root:/UAE/TM-2024-428"}}]})
    if url == f"{DELTA}?token=2":
        return httpx.Response(200, json={"@odata.deltaLink": f"{DELTA}?token=3", "value": [
            {"id": "item-9", "deleted": {"state": "deleted"}},
            {"id": "item-2", "name": "photo.jpg", "file": {}, "parentReference": {"path": "/drives/drive-1/root:/UAE"}}]})
    if url == f"{GRAPH}/drives/drive-1/items/item-1/content":
        return httpx.Response(302, headers={"Location": "https://files.example.net/blob/1?sig=abc"})
    return httpx.Response(404, json={"error": url})


def test_delta_listing_paths_and_download():
    source = SharePointSource("tenant", "client", "secret", "contoso.sharepoint.com",
                              http=httpx.Client(transport=httpx.MockTransport(graph), follow_redirects=True))
    changes = source.changes(None)
    assert changes.complete and changes.cursor == f"{DELTA}?token=3" and changes.deleted == ["item-9"]
    [f] = changes.files  # the folder and the .jpg are ignored
    assert f.key == "item-1" and f.version == "c1"
    assert f.library_path == "/sites/Legal/Cases/UAE/TM-2024-428/TM-2024-428_Judgment_EN.pdf"
    assert f.read() == b"%PDF-bytes"
    assert not source.changes(f"{DELTA}?token=2").complete  # an incremental listing is not a full listing
