from pydantic import BaseModel
from typing import List, Optional
from fastapi import HTTPException, Request, APIRouter
import math

from app.core.fastapi_config import templates


router = APIRouter(prefix="/physics/M1")


class TrajectoryRequest(BaseModel):
    angle: float
    velocity: float
    gravity: float = 9.81
    viscous_friction: float = 0.
    drag_coefficient: float = 0.


class TrajectoryPoint(BaseModel):
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
                 viscous_friction: float, drag_coefficient: float):
        self.MAX_OPERATIONS = 10 ** 3
        self.angle = math.radians(angle)  # преобразуем в радианы
        self.v0 = velocity
        self.g = gravity
        self.k_viscous = viscous_friction  # коэффициент вязкого трения
        self.k_drag = drag_coefficient  # коэффициент лобового сопротивления

        # Начальные условия
        self.x0 = 0
        self.y0 = 0
        self.vx0 = self.v0 * math.cos(self.angle)
        self.vy0 = self.v0 * math.sin(self.angle)

    def calculate_trajectory_euler(self):
        """Расчет траектории методом Эйлера с учетом сопротивления"""
        max_time = 2 * self.vy0 / self.g
        dt = max(0.01, max_time / self.MAX_OPERATIONS)

        x, y = [self.x0], [self.y0]
        vx, vy = [self.vx0], [self.vy0]
        t = 0
        times = [t]

        while y[-1] >= 0:
            t += dt

            # Текущая скорость
            current_vx = vx[-1]
            current_vy = vy[-1]
            current_v = math.sqrt(current_vx ** 2 + current_vy ** 2)

            # Силы сопротивления
            drag_force_x = -self.k_drag * current_v * current_vx  # лобовое сопротивление
            viscous_force_x = -self.k_viscous * current_vx  # вязкое трение

            drag_force_y = -self.k_drag * current_v * current_vy
            viscous_force_y = -self.k_viscous * current_vy

            # Ускорения (F = ma, для удобства предполагаем массу = 1)
            ax = drag_force_x + viscous_force_x
            ay = -self.g + drag_force_y + viscous_force_y

            # Новые скорости и координаты
            new_vx = current_vx + ax * dt
            new_vy = current_vy + ay * dt
            new_x = x[-1] + current_vx * dt
            new_y = y[-1] + current_vy * dt

            x.append(new_x)
            y.append(new_y)
            vx.append(new_vx)
            vy.append(new_vy)
            times.append(t)

            if new_y < 0:  # коррекция при падении ниже земли
                x[-1] = x[-2] + current_vx * (-y[-2] / current_vy)
                y[-1] = 0
                break

        return x, y, times


@router.get("/")
async def render_m1(request: Request):
    return templates.TemplateResponse("physics/M1.html", {
        "request": request,
    })


@router.post("/calculate", response_model=TrajectoryResponse)
async def calculate_trajectory(request: TrajectoryRequest):
    try:
        # Валидация входных данных
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

        # Создаем модель
        projectile = ProjectileMotion(
            angle=request.angle,
            velocity=request.velocity,
            gravity=request.gravity,
            viscous_friction=request.viscous_friction,
            drag_coefficient=request.drag_coefficient
        )

        # Рассчитываем траекторию
        x, y, times = projectile.calculate_trajectory_euler()

        # Подготавливаем данные для ответа
        trajectory_data = [{"x": float(x[i]), "y": float(y[i])} for i in range(len(x))]

        # Рассчитываем дополнительные параметры
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
