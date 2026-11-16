from ferrero.textproc import case_ids_in, contains, fold, index_text, is_arabic, query_terms


def test_case_ids_found_next_to_underscores_spaces_and_arabic():
    assert case_ids_in("TM-2024-403_judgment.pdf") == ["TM-2024-403"]
    assert case_ids_in("حكم TM-2026-417.pdf") == ["TM-2026-417"]
    assert case_ids_in("judgment tm-2024-400 (1).pdf") == ["TM-2024-400"]
    assert case_ids_in("TM-2024-4031") == []  # not a case number


def test_arabic_variants_meet_in_one_stem():
    variants = ["العلامة", "العلامات", "علامة", "والعلامة"]
    assert len({index_text(v) for v in variants}) == 1
    assert index_text("تعويضاً") == index_text("التعويض") == index_text("بتعويض")


def test_folding_handles_presentation_forms_and_digits():
    assert fold("ﺣﻜﻢ") == "حكم"            # Arabic presentation forms -> letters
    assert fold("١٢٣") == "123"             # Arabic-Indic digits
    assert contains(fold("محكمة دبي الابتدائية"), "محكمه دبي")


def test_query_terms_drop_stop_words_and_case_numbers():
    assert query_terms("What damages were awarded in TM-2024-428?") == ["damages", "awarded"]
    assert "القضيه" not in query_terms("ما مبلغ التعويض في القضية TM-2024-428؟")


def test_is_arabic():
    assert is_arabic("الحكم لصالح المدعية بتعويض قدره 1,694,000 ريال")
    assert not is_arabic("AED 2,288,000 was awarded (فيلورا)")
