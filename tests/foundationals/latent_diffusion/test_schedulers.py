import pytest
from typing import cast
from warnings import warn
from refiners.foundationals.latent_diffusion.schedulers import Scheduler, DPMSolver, DDIM
from refiners.fluxion import norm, manual_seed
from torch import linspace, float32, randn, Tensor, allclose, device as Device


def test_scheduler_utils():
    class DummyScheduler(Scheduler):
        def __call__(self, x: Tensor, noise: Tensor, step: int) -> Tensor:
            return Tensor()

        def _generate_timesteps(self) -> Tensor:
            return Tensor()

    scheduler = DummyScheduler(10, 20, 0.1, 0.2, "cpu")
    scale_factors = (
        1.0
        - linspace(
            start=0.1**0.5,
            end=0.2**0.5,
            steps=20,
            dtype=float32,
        )
        ** 2
    )
    assert norm(scheduler.scale_factors - scale_factors) == 0


def test_dpm_solver_diffusers():
    from diffusers import DPMSolverMultistepScheduler as DiffuserScheduler  # type: ignore

    manual_seed(0)

    diffusers_scheduler = DiffuserScheduler(beta_schedule="scaled_linear", beta_start=0.00085, beta_end=0.012)
    diffusers_scheduler.set_timesteps(30)
    refiners_scheduler = DPMSolver(num_inference_steps=30)

    sample = randn(1, 3, 32, 32)
    noise = randn(1, 3, 32, 32)

    for step, timestep in enumerate(diffusers_scheduler.timesteps):
        diffusers_output = cast(Tensor, diffusers_scheduler.step(noise, timestep, sample).prev_sample)  # type: ignore
        refiners_output = refiners_scheduler(x=sample, noise=noise, step=step)
        assert allclose(diffusers_output, refiners_output), f"outputs differ at step {step}"


def test_ddim_solver_diffusers():
    from diffusers import DDIMScheduler  # type: ignore

    diffusers_scheduler = DDIMScheduler(
        beta_end=0.012,
        beta_schedule="scaled_linear",
        beta_start=0.00085,
        num_train_timesteps=1000,
        set_alpha_to_one=False,
        steps_offset=1,
        clip_sample=False,
    )
    diffusers_scheduler.set_timesteps(30)
    refiners_scheduler = DDIM(num_inference_steps=30)

    sample = randn(1, 4, 32, 32)
    noise = randn(1, 4, 32, 32)

    for step, timestep in enumerate(diffusers_scheduler.timesteps):
        diffusers_output = cast(Tensor, diffusers_scheduler.step(noise, timestep, sample).prev_sample)  # type: ignore
        refiners_output = refiners_scheduler(x=sample, noise=noise, step=step)

        assert allclose(diffusers_output, refiners_output, rtol=0.01), f"outputs differ at step {step}"


def test_scheduler_remove_noise():
    from diffusers import DDIMScheduler  # type: ignore

    diffusers_scheduler = DDIMScheduler(
        beta_end=0.012,
        beta_schedule="scaled_linear",
        beta_start=0.00085,
        num_train_timesteps=1000,
        set_alpha_to_one=False,
        steps_offset=1,
        clip_sample=False,
    )
    diffusers_scheduler.set_timesteps(30)
    refiners_scheduler = DDIM(num_inference_steps=30)

    sample = randn(1, 4, 32, 32)
    noise = randn(1, 4, 32, 32)

    for step, timestep in enumerate(diffusers_scheduler.timesteps):
        diffusers_output = cast(Tensor, diffusers_scheduler.step(noise, timestep, sample).pred_original_sample)  # type: ignore
        refiners_output = refiners_scheduler.remove_noise(x=sample, noise=noise, step=step)

        assert allclose(diffusers_output, refiners_output, rtol=0.01), f"outputs differ at step {step}"


def test_scheduler_device(test_device: Device):
    if test_device.type == "cpu":
        warn("not running on CPU, skipping")
        pytest.skip()

    scheduler = DDIM(num_inference_steps=30, device=test_device)
    x = randn(1, 4, 32, 32, device=test_device)
    noise = randn(1, 4, 32, 32, device=test_device)
    noised = scheduler.add_noise(x, noise, scheduler.steps[0])
    assert noised.device == test_device
