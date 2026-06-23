from sxml_agent.escaner import escanear, hash_archivo

def test_escanear_solo_xml_recursivo(tmp_path):
    (tmp_path / "a.xml").write_text("<a/>", encoding="utf-8")
    (tmp_path / "nota.pdf").write_bytes(b"%PDF")
    sub = tmp_path / "sub"; sub.mkdir()
    (sub / "b.xml").write_text("<b/>", encoding="utf-8")
    (sub / "c.txt").write_text("x", encoding="utf-8")
    res = escanear([str(tmp_path)])
    assert sorted(p.name for p in res) == ["a.xml", "b.xml"]

def test_escanear_carpeta_inexistente_se_omite(tmp_path):
    (tmp_path / "a.xml").write_text("<a/>", encoding="utf-8")
    res = escanear([str(tmp_path), str(tmp_path / "noexiste")])
    assert [p.name for p in res] == ["a.xml"]

def test_hash_archivo_estable_y_sensible(tmp_path):
    f = tmp_path / "x.xml"; f.write_text("<a/>", encoding="utf-8")
    h1 = hash_archivo(f)
    assert h1 == hash_archivo(f)
    assert len(h1) == 64
    f.write_text("<b/>", encoding="utf-8")
    assert hash_archivo(f) != h1

def test_escanear_deduplica_misma_carpeta(tmp_path):
    (tmp_path / "a.xml").write_text("<a/>", encoding="utf-8")
    res = escanear([str(tmp_path), str(tmp_path)])  # misma carpeta dos veces
    assert len(res) == 1
