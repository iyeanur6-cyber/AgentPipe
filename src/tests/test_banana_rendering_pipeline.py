from banana_rendering_pipeline import (
    BANANA_TO_PUDDING_FLAG,
    BananaPrimitive,
    BananaRenderingPipeline,
    render_banana_stash_image,
)


def test_render_writes_valid_ppm_image(tmp_path):
    output = tmp_path / "stash.ppm"
    result = render_banana_stash_image(
        [
            {"x": -0.45, "y": 0.1, "z": 0.0, "length": 1.2, "curvature": 0.35},
            {"x": 0.35, "y": -0.2, "z": 0.3, "length": 0.9, "ripeness": 0.55},
        ],
        output,
        width=64,
        height=48,
    )

    assert result.mode == "banana"
    assert result.output_path == output
    assert output.read_bytes().startswith(b"P6\n64 48\n255\n")
    assert len(result.image_bytes) == len(b"P6\n64 48\n255\n") + 64 * 48 * 3


def test_render_is_deterministic_for_same_3d_data():
    pipeline = BananaRenderingPipeline(width=72, height=54)
    stash = [
        BananaPrimitive(center=(-0.2, 0.0, 0.1), length=1.0, curvature=0.25),
        BananaPrimitive(center=(0.25, 0.15, -0.1), length=0.8, ripeness=0.6),
    ]

    first = pipeline.render(stash)
    second = pipeline.render(stash)

    assert first.image_bytes == second.image_bytes


def test_binary_flag_transforms_bananas_into_pudding():
    pipeline = BananaRenderingPipeline(width=80, height=60)
    stash = [
        (-0.5, 0.0, 0.0, 1.1),
        (0.3, 0.2, 0.2, 0.7),
    ]

    banana = pipeline.render(stash)
    pudding = pipeline.render(stash, transform_flags=BANANA_TO_PUDDING_FLAG)

    assert pudding.mode == "banana-pudding"
    assert pudding.transform_flags == BANANA_TO_PUDDING_FLAG
    assert pudding.image_bytes != banana.image_bytes
    assert bytes((236, 198, 122)) in pudding.image_bytes


def test_explicit_pudding_mode_uses_3d_input_without_flag():
    result = BananaRenderingPipeline(width=48, height=48).render(
        [{"x": 0, "y": 0, "z": 0, "length": 1.0}],
        as_pudding=True,
    )

    assert result.mode == "banana-pudding"
    assert result.width == 48
    assert result.height == 48
