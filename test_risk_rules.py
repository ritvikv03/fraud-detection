from risk_rules import label_risk, score_transaction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_tx(**overrides) -> dict:
    """Base transaction with zero risk; override individual fields per test."""
    base = {
        "device_risk_score": 5,
        "is_international": 0,
        "amount_usd": 50.0,
        "velocity_24h": 1,
        "failed_logins_24h": 0,
        "prior_chargebacks": 0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# label_risk thresholds
# ---------------------------------------------------------------------------

def test_label_risk_low():
    assert label_risk(0) == "low"
    assert label_risk(29) == "low"


def test_label_risk_medium_boundary():
    assert label_risk(30) == "medium"
    assert label_risk(59) == "medium"


def test_label_risk_high_boundary():
    assert label_risk(60) == "high"
    assert label_risk(100) == "high"


# ---------------------------------------------------------------------------
# Device risk score
# ---------------------------------------------------------------------------

def test_low_device_risk_adds_no_points():
    score = score_transaction(clean_tx(device_risk_score=39))
    assert score == 0


def test_medium_device_risk_adds_points():
    score = score_transaction(clean_tx(device_risk_score=40))
    assert score == 10


def test_high_device_risk_adds_more_points():
    score_medium = score_transaction(clean_tx(device_risk_score=40))
    score_high = score_transaction(clean_tx(device_risk_score=70))
    assert score_high > score_medium
    assert score_high == 25


def test_device_risk_at_69_uses_medium_tier():
    score = score_transaction(clean_tx(device_risk_score=69))
    assert score == 10


# ---------------------------------------------------------------------------
# International flag
# ---------------------------------------------------------------------------

def test_international_increases_score():
    domestic = score_transaction(clean_tx(is_international=0))
    intl = score_transaction(clean_tx(is_international=1))
    assert intl > domestic
    assert intl - domestic == 15


def test_domestic_transaction_no_international_penalty():
    score = score_transaction(clean_tx(is_international=0))
    assert score == 0


# ---------------------------------------------------------------------------
# Amount tiers
# ---------------------------------------------------------------------------

def test_small_amount_adds_no_points():
    score = score_transaction(clean_tx(amount_usd=499.99))
    assert score == 0


def test_medium_amount_adds_points():
    score = score_transaction(clean_tx(amount_usd=500.0))
    assert score == 10


def test_large_amount_adds_more_points():
    score = score_transaction(clean_tx(amount_usd=1000.0))
    assert score == 25


def test_large_amount_boundary_999():
    score = score_transaction(clean_tx(amount_usd=999.99))
    assert score == 10


# ---------------------------------------------------------------------------
# Velocity
# ---------------------------------------------------------------------------

def test_low_velocity_adds_no_points():
    score = score_transaction(clean_tx(velocity_24h=2))
    assert score == 0


def test_medium_velocity_adds_points():
    score = score_transaction(clean_tx(velocity_24h=3))
    assert score == 5


def test_high_velocity_adds_more_points():
    score_medium = score_transaction(clean_tx(velocity_24h=3))
    score_high = score_transaction(clean_tx(velocity_24h=6))
    assert score_high > score_medium
    assert score_high == 20


def test_velocity_at_5_uses_medium_tier():
    score = score_transaction(clean_tx(velocity_24h=5))
    assert score == 5


# ---------------------------------------------------------------------------
# Failed logins
# ---------------------------------------------------------------------------

def test_no_failed_logins_adds_no_points():
    score = score_transaction(clean_tx(failed_logins_24h=0))
    assert score == 0


def test_some_failed_logins_add_points():
    score = score_transaction(clean_tx(failed_logins_24h=2))
    assert score == 10


def test_many_failed_logins_add_more_points():
    score_some = score_transaction(clean_tx(failed_logins_24h=2))
    score_many = score_transaction(clean_tx(failed_logins_24h=5))
    assert score_many > score_some
    assert score_many == 20


def test_failed_logins_at_4_uses_lower_tier():
    score = score_transaction(clean_tx(failed_logins_24h=4))
    assert score == 10


# ---------------------------------------------------------------------------
# Prior chargebacks
# ---------------------------------------------------------------------------

def test_no_prior_chargebacks_adds_no_points():
    score = score_transaction(clean_tx(prior_chargebacks=0))
    assert score == 0


def test_one_prior_chargeback_adds_points():
    score = score_transaction(clean_tx(prior_chargebacks=1))
    assert score == 5


def test_multiple_prior_chargebacks_add_more_points():
    score_one = score_transaction(clean_tx(prior_chargebacks=1))
    score_multiple = score_transaction(clean_tx(prior_chargebacks=2))
    assert score_multiple > score_one
    assert score_multiple == 20


def test_three_chargebacks_same_as_two():
    assert score_transaction(clean_tx(prior_chargebacks=3)) == score_transaction(clean_tx(prior_chargebacks=2))


# ---------------------------------------------------------------------------
# Combined scenarios
# ---------------------------------------------------------------------------

def test_clean_transaction_scores_zero():
    """A completely clean transaction should score 0."""
    assert score_transaction(clean_tx()) == 0


def test_high_risk_transaction_scores_high():
    """A transaction hitting every risk signal should be labeled high."""
    tx = clean_tx(
        device_risk_score=85,
        is_international=1,
        amount_usd=1500.0,
        velocity_24h=8,
        failed_logins_24h=6,
        prior_chargebacks=3,
    )
    assert score_transaction(tx) >= 60
    assert label_risk(score_transaction(tx)) == "high"


def test_score_clamped_at_100():
    """Score must never exceed 100 even with every signal firing."""
    tx = clean_tx(
        device_risk_score=99,
        is_international=1,
        amount_usd=9999.0,
        velocity_24h=99,
        failed_logins_24h=99,
        prior_chargebacks=99,
    )
    assert score_transaction(tx) == 100


def test_score_never_negative():
    """Score must never fall below 0."""
    assert score_transaction(clean_tx()) >= 0


def test_international_high_device_high_velocity_is_high_risk():
    """Core fraud pattern: international + bad device + velocity burst."""
    tx = clean_tx(device_risk_score=75, is_international=1, velocity_24h=7)
    score = score_transaction(tx)
    assert label_risk(score) == "high"


def test_chargeback_history_pushes_medium_to_high():
    """A borderline medium-risk account tips to high when it has chargeback history."""
    without_cb = clean_tx(amount_usd=1000.0, velocity_24h=3)
    with_cb = clean_tx(amount_usd=1000.0, velocity_24h=3, prior_chargebacks=2)
    assert score_transaction(with_cb) > score_transaction(without_cb)
