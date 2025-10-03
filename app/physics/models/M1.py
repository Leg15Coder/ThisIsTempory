from pydantic import BaseModel
from typing import List, Optional
from fastapi import HTTPException, Request, APIRouter
import math

from app.core.fastapi_config import templates


router = APIRouter(prefix="/physics/M1")


class TrajectoryRequest(BaseModel):
    mass: float = 1.
    angle: float
    velocity: float
    gravity: float = 9.81
    viscous_friction: float = 0.
    drag_coefficient: float = 0.


class TrajectoryPoint(BaseModel):
    dt: float
    x: float
    y: float


class TrajectoryStats(BaseModel):
    flight_time: float
    max_height: float
    range: float


class TrajectoryResponse(BaseModel):
    success: bool
    trajectory: List[TrajectoryPoint]
    stats: TrajectoryStats


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


class ProjectileMotion:
    def __init__(self, angle: float, velocity: float, gravity: float,
                 viscous_friction: float, drag_coefficient: float, mass: float):
        self.MAX_OPERATIONS = 4 * 10 ** 2
        self.ACCURACY = 0.05
        self.angle = math.radians(angle)
        self.v0 = velocity
        self.g = gravity
        self.mass = mass
        self.k_viscous = viscous_friction
        self.k_drag = drag_coefficient

        self.x0 = 0
        self.y0 = 0
        self.vx0 = self.v0 * math.cos(self.angle)
        self.vy0 = self.v0 * math.sin(self.angle)

    def _calculate_step(self, x, y, current_vx, current_vy, dt):
        current_v = math.sqrt(current_vx ** 2 + current_vy ** 2)

        drag_force_x = -self.k_drag * current_v * current_vx
        viscous_force_x = -self.k_viscous * current_vx

        drag_force_y = -self.k_drag * current_v * current_vy
        viscous_force_y = -self.k_viscous * current_vy

        ax = (drag_force_x + viscous_force_x) / self.mass
        ay = -self.g + (drag_force_y + viscous_force_y) / self.mass

        new_vx = max(current_vx + ax * dt, 0)
        new_vy = current_vy + ay * dt
        new_x = x + current_vx * dt
        new_y = y + current_vy * dt

        return new_x, new_y, new_vx, new_vy

    def calculate_trajectory_euler(self):
        max_time = 2 * self.vy0 / self.g
        dt = max_time / self.MAX_OPERATIONS
        const = 10.0
        p_const = 1.0
        x, y = [self.x0], [self.y0]
        t = 0
        times = [t]

        while len(x) < self.MAX_OPERATIONS / 4:
            x, y = [self.x0], [self.y0]
            vx, vy = [self.vx0], [self.vy0]
            t = 0
            times = [t]

            while y[-1] >= 0:
                new_x, new_y, new_vx, new_vy = self._calculate_step(x[-1], y[-1], vx[-1], vy[-1], dt)
                new_x_half, new_y_half, new_vx_half, new_vy_half = self._calculate_step(x[-1], y[-1], vx[-1], vy[-1], dt/2)

                err = math.sqrt((new_vx - new_vx_half) ** 2 + (new_vy - new_vy_half) ** 2) / math.sqrt(vx[-1] ** 2 + vy[-1] ** 2 + self.ACCURACY / 100.0)

                if err > self.ACCURACY * p_const:
                    dt = dt / 2
                    continue
                elif err < self.ACCURACY / const:
                    dt *= 1.5
                    continue

                x.append(new_x)
                y.append(new_y)
                vx.append(new_vx)
                vy.append(new_vy)

                t += dt
                times.append(t)

                if new_y < 0 and x[-2] != x[-1]:
                    k = (y[-2] - y[-1]) / (x[-2] - x[-1])
                    b = y[-1] - x[-1] * k

                    if k == 0:
                        x[-1] -= vx[-1] * dt
                        y[-1] = 0
                        break

                    x[-1] = -b / k
                    y[-1] = 0
                    break
                elif 90 - self.angle < 1e-6:
                    y[-1] = 0
                    break

            const *= 1.05
            p_const *= 0.95

        return x, y, times


@router.get("/")
async def render_m1(request: Request):
    return templates.TemplateResponse("physics/M1.html", {
        "request": request,
    })


@router.post("/calculate", response_model=TrajectoryResponse)
async def calculate_trajectory(request: TrajectoryRequest):
    try:
        if request.mass <= 0:
            raise HTTPException(status_code=400, detail="Масса должна быть положительна")
        if not (0 <= request.angle <= 90):
            raise HTTPException(status_code=400, detail="Угол должен быть между 0 и 90 градусами")
        if request.velocity <= 0:
            raise HTTPException(status_code=400, detail="Скорость должна быть положительной")
        if request.gravity <= 0:
            raise HTTPException(status_code=400, detail="Ускорение свободного падения должно быть положительным")
        if request.viscous_friction < 0:
            raise HTTPException(status_code=400, detail="Коэффициент вязкого трения не может быть отрицательным")
        if request.drag_coefficient < 0:
            raise HTTPException(status_code=400, detail="Коэффициент лобового трения не может быть отрицательным")

        projectile = ProjectileMotion(
            mass=request.mass,
            angle=request.angle,
            velocity=request.velocity,
            gravity=request.gravity,
            viscous_friction=request.viscous_friction,
            drag_coefficient=request.drag_coefficient
        )

        x, y, times = projectile.calculate_trajectory_euler()

        trajectory_data = [{"x": float(x[i]), "y": float(y[i]), "dt": times[i] if i == 0 else times[i] - times[i-1]} for i in range(len(x))]

        flight_time = times[-1]
        max_height = max(y)
        range_distance = x[-1]

        return TrajectoryResponse(
            success=True,
            trajectory=trajectory_data,
            stats={
                "flight_time": flight_time,
                "max_height": max_height,
                "range": range_distance
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при расчете траектории: {str(e)}")
