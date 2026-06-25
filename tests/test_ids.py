from hindsight_local.ids import document_id, entity_id


def test_document_id_is_stable():
    assert document_id("x", "hello") == document_id("x", "hello")


def test_entity_id_normalizes_case():
    assert entity_id("default", "Calvin") == entity_id("default", " calvin ")
