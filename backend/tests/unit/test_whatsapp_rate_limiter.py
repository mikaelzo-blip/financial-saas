from src.services.integrations.whatsapp.rate_limiter import SlidingWindowRateLimiter


def test_sliding_window_and_single_warning():
    now = [0.0]
    limiter = SlidingWindowRateLimiter(clock=lambda: now[0])
    for _ in range(20):
        assert limiter.check("phone", 20) == (True, False)
    assert limiter.check("phone", 20) == (False, True)
    assert limiter.check("phone", 20) == (False, False)
    assert limiter.check("other", 20) == (True, False)
    now[0] = 60
    assert limiter.check("phone", 20) == (True, False)


def test_cardinality_is_bounded():
    limiter = SlidingWindowRateLimiter(max_keys=2)
    assert limiter.check("a", 20)[0]
    assert limiter.check("b", 20)[0]
    assert not limiter.check("c", 20)[0]
