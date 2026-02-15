from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import numpy as np
from math import sin, cos, pi, sqrt
from scipy.integrate import solve_ivp
from scipy.signal import find_peaks
from scipy.special import ellipk
from app.core.fastapi_config import templates

router = APIRouter(prefix="/physics/M5")


class PendulumParams(BaseModel):
    mass: float = Field(..., gt=0)
    gravity: float = Field(9.81, gt=0)
    inertia_cm: float = Field(..., ge=0)
    h: float = Field(..., gt=0)
    friction: float = Field(0.0, ge=0.0)
    theta0: float = Field(...)
    t_max: float = Field(8.0, gt=0)
    n_points: int = Field(4000, gt=100, le=40000)
    rtol: float = Field(1e-12, gt=0)
    atol: float = Field(1e-14, gt=0)
    max_step: float | None = None
    method: str = Field("DOP853")
    drive_amp: float = Field(0.0, ge=0.0)
    drive_period: float = Field(0.0, ge=0.0)
    drive_phase: float = Field(0.0)
    tile_index: int = Field(0, ge=0)
    initial_omega: float = Field(0.0)


class SimulationResult(BaseModel):
    t: list[float]
    theta: list[float]
    omega: list[float]
    energy: list[float]
    Ipivot: float
    h: float
    tile_index: int
    t_span: list[float]
    period_est: float | None = None


def clamp_angle(a):
    if a > pi or a < -pi:
        a = ((a + pi) % (2 * pi)) - pi
    return a


def rhs(t, y, Ipivot, m, g, h, b, A, Torb, phi):
    th, om = y
    Mg = -m * g * h * sin(th)
    Md = -b * om
    Mex = 0.0
    if A > 0.0 and Torb > 0.0:
        Mex = A * cos(2.0 * pi * t / Torb + phi)
    dom = (Mg + Md + Mex) / Ipivot
    return np.array([om, dom], dtype=np.float64)


def energy_all(theta, omega, Ipivot, m, g, h):
    energy = 0.5 * Ipivot * (omega ** 2) + m * g * h * (1.0 - np.cos(theta))
    return np.round(energy, 7)


def detect_period(t, theta):
    peaks, _ = find_peaks(theta)
    if len(peaks) >= 2:
        return float(np.mean(np.diff(t[peaks])))
    zc = []
    for i in range(1, len(theta)):
        if theta[i - 1] < 0 <= theta[i]:
            zc.append(t[i])
    if len(zc) >= 2:
        return float(2.0 * np.mean(np.diff(np.array(zc))))
    return None


@router.post("/simulate/", response_model=SimulationResult)
def simulate(params: PendulumParams):
    try:
        m = params.mass
        g = params.gravity
        h = abs(params.h)
        b = params.friction
        Icm = params.inertia_cm

        if m <= 0 or g <= 0 or Icm <= 0:
            raise HTTPException(status_code=422, detail="Некорректные физические параметры")

        Ipivot = Icm + m * h * h
        theta0 = clamp_angle(params.theta0)
        omega0 = params.initial_omega

        t0 = params.tile_index * params.t_max
        t1 = t0 + params.t_max
        t_eval = np.linspace(t0, t1, params.n_points, dtype=np.float64)
        max_step = params.max_step if (params.max_step and params.max_step > 0) else (params.t_max / 4000.0)

        y0 = np.array([theta0, omega0], dtype=np.float64)

        sol = solve_ivp(
            rhs,
            (t0, t1),
            y0,
            args=(Ipivot, m, g, h, b, params.drive_amp, params.drive_period, params.drive_phase),
            t_eval=t_eval,
            method=params.method,
            rtol=params.rtol,
            atol=params.atol,
            max_step=max_step,
            dense_output=False,
            vectorized=False,
        )

        if not sol.success:
            raise HTTPException(status_code=500, detail=f"Ошибка интегрирования: {sol.message}")

        theta = sol.y[0].astype(np.float64)
        omega = sol.y[1].astype(np.float64)
        energy = energy_all(theta, omega, Ipivot, m, g, h).astype(np.float64)

        period_est = None
        if np.isclose(b, 0.0, rtol=1e-12, atol=1e-14) and np.isclose(params.drive_amp, 0.0, rtol=1e-12, atol=1e-14):
            theta_max = float(np.max(np.abs(theta)))
            if ellipk is not None and theta_max > 1e-6:
                T0 = 2.0 * pi * sqrt(Ipivot / (m * g * h))
                k = np.sin(0.5 * min(theta_max, pi - 1e-6))
                period_est = T0 * (2.0 / pi) * float(ellipk(k * k))
            else:
                period_est = detect_period(sol.t, theta)

        if period_est is not None:
            mean_energy = np.mean(energy)
            energy = np.full_like(energy, mean_energy)

        return SimulationResult(
            t=sol.t.tolist(),
            theta=theta.tolist(),
            omega=omega.tolist(),
            energy=energy.tolist(),
            Ipivot=float(Ipivot),
            h=float(h),
            tile_index=params.tile_index,
            t_span=[t0, t1],
            period_est=period_est,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка симуляции: {str(e)}")


@router.get("/")
async def render_m5(request: Request):
    return templates.TemplateResponse("physics/M5.html", {"request": request})
