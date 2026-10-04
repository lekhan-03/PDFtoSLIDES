def test_pdf_spans_groups_correctly():
    import src.pdf_spans as pdf_spans
    
    # Mock pdict with lines and spans
    pdict = {
        "blocks": [
            {
                "type": 0,
                "lines": [
                    {
                        "bbox": (10, 20, 100, 30),
                        "spans": [
                            {"text": "A line ", "bbox": (10, 20, 50, 30), "size": 12},
                            {"text": "2+", "bbox": (50, 15, 60, 25), "size": 8}
                        ]
                    }
                ]
            }
        ]
    }
    
    items = pdf_spans.page_items(pdict, 1)
    
    assert len(items) == 2
    assert items[0]["text"] == "A line"
    assert items[0]["line_y0"] == 20
    assert items[1]["text"] == "2+"
    assert items[1]["line_y0"] == 20
