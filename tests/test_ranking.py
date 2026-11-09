from src.ranking import calculate_ranking


def test_ranking_orders_by_weighted_score():
    quality = [
        {"image_id": "a", "quality_score": 8.0},
        {"image_id": "b", "quality_score": 6.0},
    ]
    aesthetics = [
        {"image_id": "a", "aesthetic_score": 7.0},
        {"image_id": "b", "aesthetic_score": 9.0},
    ]
    result = calculate_ranking(quality, aesthetics)
    assert result[0]["image_id"] == "a"
    assert result[0]["rank"] == 1
