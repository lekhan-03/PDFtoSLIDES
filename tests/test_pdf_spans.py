from pdf_spans import spans_to_text, page_items


def sp(text, size, y, x0=0, x1=0):
    return {"text": text, "size": size, "origin": (x0, y), "bbox": (x0, y - size, x1 or x0 + len(text) * 6, y + 3)}


def test_q42_charges_from_the_real_spans():            # spans copied from the Stage 2f output
    spans = [sp("42.", 12.0, 496.39), sp(" ", 12.0, 496.39), sp("The E° values of Fe", 12.0, 496.39),
             sp("2+", 8.04, 491.83), sp(" / Fe, Zn", 12.0, 496.39), sp("2+", 8.04, 491.83),
             sp(" / Zn, and Sn", 12.0, 496.39), sp("2+", 8.04, 491.83),
             sp(" / Sn are -0.44V, -0.76V, and -0.14V ", 12.0, 496.39)]
    assert spans_to_text(spans) == "42. The E° values of Fe²⁺ / Fe, Zn²⁺ / Zn, and Sn²⁺ / Sn are -0.44V, -0.76V, and -0.14V "


def test_subscripts_and_exponents():
    assert spans_to_text([sp("2NO", 12, 100), sp("2", 8, 103), sp("(g)", 12, 100)]) == "2NO₂(g)"
    assert spans_to_text([sp("SO", 12, 100), sp("4", 8, 103), sp("2-", 8, 96)]) == "SO₄²⁻"
    assert spans_to_text([sp("Rate = k[NO]", 12, 100), sp("2", 8, 96), sp("[O", 12, 100), sp("2", 8, 103), sp("]", 12, 100)]) == "Rate = k[NO]²[O₂]"
    assert spans_to_text([sp("e", 12, 100), sp("x", 8, 96)]) == "eˣ"
    assert spans_to_text([sp("x", 12, 100), sp("2n+1", 8, 96)]) == "x²ⁿ⁺¹"
    assert spans_to_text([sp("x", 12, 100), sp("q", 8, 96)]) == "x^{q}"            # not mappable -> ^{..} marker


def test_small_text_on_the_baseline_is_left_alone():    # e.g. small-caps or a footnote marker on the same baseline
    assert spans_to_text([sp("Note", 12, 100), sp("small", 8, 100)]) == "Notesmall"


def test_page_items_keep_the_charge_with_its_own_line_and_split_columns():
    line42 = {"bbox": (63, 484, 520, 502),
              "spans": [sp("42. Fe", 12, 496.39, 63, 100), sp("2+", 8.04, 491.83, 100, 112), sp(" / Fe", 12, 496.39, 112, 140)]}
    line41 = {"bbox": (63, 460, 520, 478), "spans": [sp("Statement II is correct", 12, 472.0, 63, 200)]}
    cols = {"bbox": (90, 520, 400, 538),
            "spans": [sp("(A) Zero order kinetics", 12, 532, 90, 230), sp("(B) Half-order kinetics", 12, 532, 270, 410)]}
    page = {"blocks": [{"type": 0, "lines": [line42, line41, cols]}]}
    items = page_items(page, 7)
    assert [i["text"] for i in items] == ["Statement II is correct", "42. Fe²⁺ / Fe", "(A) Zero order kinetics",
                                          "(B) Half-order kinetics"], [i["text"] for i in items]


if __name__ == "__main__":
    for f in (test_q42_charges_from_the_real_spans, test_subscripts_and_exponents,
              test_small_text_on_the_baseline_is_left_alone, test_page_items_keep_the_charge_with_its_own_line_and_split_columns):
        f(); print("ok ", f.__name__)
