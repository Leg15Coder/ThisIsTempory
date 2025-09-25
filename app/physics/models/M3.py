from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from app.core.fastapi_config import templates
import math
from datetime import datetime, timedelta

router = APIRouter(prefix='/physics/M3')


class MissionPhase(str, Enum):
    LAUNCH = "launch"
    TRANSFER = "transfer"
    LANDING = "landing"


class MarsMissionRequest(BaseModel):
    # Параметры запуска
    initial_mass: float = 1000000  # кг
    thrust: float = 20000000  # Н
    specific_impulse: float = 350  # с
    launch_angle: float = 90  # градусы (вертикальный взлет)

    # Параметры перелета
    departure_date: str = "2024-01-01"
    transfer_time: float = 200  # дней

    # Параметры посадки
    landing_mass: float = 10000  # кг
    landing_thrust: float = 500000  # Н
    landing_angle: float = -90  # градусы

    # Дополнительные параметры
    include_atmosphere: bool = False
    include_planetary_gravity: bool = False
    include_orientation: bool = False


class TrajectoryPoint(BaseModel):
    x: float
    y: float
    z: float
    time: float
    velocity: float
    mass: float
    phase: MissionPhase


class MissionStats(BaseModel):
    total_time: float
    delta_v: float
    fuel_consumed: float
    max_acceleration: float
    arrival_velocity: float


class MarsMissionResponse(BaseModel):
    success: bool
    trajectory: List[TrajectoryPoint]
    stats: MissionStats
    planetary_positions: Dict[str, List[float]]


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


# Константы
G = 6.67430e-11  # гравитационная постоянная
M_SUN = 1.989e30  # масса Солнца
M_EARTH = 5.972e24  # масса Земли
M_MARS = 6.39e23  # масса Марса
R_EARTH = 6371000  # радиус Земли
R_MARS = 3389500  # радиус Марса
AU = 1.496e11  # астрономическая единица


class MarsMissionSimulator:
    def __init__(self, request: MarsMissionRequest):
        self.request = request
        self.trajectory = []

    def calculate_launch_phase(self):
        """Фаза 1: Вертикальный взлет с Земли"""
        dt = 1.0  # шаг времени в секундах
        t = 0
        mass = self.request.initial_mass
        altitude = 0
        velocity = 0
        phase = MissionPhase.LAUNCH

        # Параметры атмосферы (если включено)
        rho0 = 1.225 if self.request.include_atmosphere else 0
        H = 8500

        while altitude < 200000:  # до высоты 200 км
            # Сила тяги
            thrust = self.request.thrust

            # Расход топлива
            dm_dt = thrust / (self.request.specific_impulse * 9.81)
            mass -= dm_dt * dt

            if mass <= self.request.landing_mass:
                break

            # Гравитация
            g = G * M_EARTH / (R_EARTH + altitude) ** 2

            # Сопротивление атмосферы (если включено)
            if self.request.include_atmosphere and altitude < 100000:
                rho = rho0 * math.exp(-altitude / H)
                drag = 0.5 * rho * velocity ** 2 * 0.3  # Cd * A примерно
            else:
                drag = 0

            # Ускорение
            acceleration = (thrust - mass * g - drag) / mass

            # Интегрирование
            velocity += acceleration * dt
            altitude += velocity * dt
            t += dt

            self.trajectory.append(TrajectoryPoint(
                x=0, y=altitude, z=0,
                time=t, velocity=velocity,
                mass=mass, phase=phase
            ))

        return mass, velocity, altitude

    def calculate_transfer_phase(self, initial_mass: float, initial_velocity: float):
        """Фаза 2: Перелет Земля-Марс"""
        dt = 3600  # шаг времени в час
        t = self.trajectory[-1].time if self.trajectory else 0
        phase = MissionPhase.TRANSFER

        # Начальные условия на орбите Земли
        r_earth = 1.0 * AU
        v_earth = 29.78e3

        # Положение Марса
        r_mars = 1.524 * AU
        v_mars = 24.07e3

        # Начальная скорость (орбитальная + дополнительная)
        v0 = math.sqrt(v_earth ** 2 + initial_velocity ** 2)

        # Положение и скорость
        r = r_earth
        v = v0
        theta = 0  # угловая позиция

        mass = initial_mass

        while r < r_mars:
            # Гравитация Солнца
            a_sun = -G * M_SUN / r ** 2

            # Гравитация планет (если включено)
            if self.request.include_planetary_gravity:
                # Упрощенная модель - планеты в фиксированных позициях
                dist_to_earth = abs(r - r_earth)
                dist_to_mars = abs(r - r_mars)

                a_earth = G * M_EARTH / max(dist_to_earth, 0.1 * AU) ** 2
                a_mars = G * M_MARS / max(dist_to_mars, 0.1 * AU) ** 2

                # Направление гравитации
                if r < r_earth:
                    a_earth = -a_earth
                if r < r_mars:
                    a_mars = -a_mars
            else:
                a_earth = a_mars = 0

            total_a = a_sun + a_earth + a_mars

            # Интегрирование
            v += total_a * dt
            r += v * dt
            theta += (v / r) * dt

            t += dt

            # Преобразование в декартовы координаты
            x = r * math.cos(theta)
            y = r * math.sin(theta)

            self.trajectory.append(TrajectoryPoint(
                x=x, y=y, z=0,
                time=t, velocity=v,
                mass=mass, phase=phase
            ))

            if r >= r_mars:
                break

        return mass, v, r

    def calculate_landing_phase(self, initial_mass: float, approach_velocity: float):
        """Фаза 3: Посадка на Марс"""
        dt = 0.1  # маленький шаг времени
        t = self.trajectory[-1].time if self.trajectory else 0
        phase = MissionPhase.LANDING

        altitude = 100000  # начальная высота
        velocity = approach_velocity
        mass = initial_mass

        while altitude > 0 and mass > self.request.landing_mass * 0.9:
            # Гравитация Марса
            g = G * M_MARS / (R_MARS + altitude) ** 2

            # Сила тяги (торможение)
            thrust = min(self.request.landing_thrust, mass * g * 1.2)  # немного больше g

            # Расход топлива
            dm_dt = thrust / (self.request.specific_impulse * 9.81)
            mass -= dm_dt * dt

            # Ускорение
            acceleration = (thrust - mass * g) / mass

            # Интегрирование
            velocity += acceleration * dt
            altitude -= velocity * dt
            t += dt

            self.trajectory.append(TrajectoryPoint(
                x=0, y=altitude, z=0,
                time=t, velocity=velocity,
                mass=mass, phase=phase
            ))

            if altitude <= 0:
                break

        return mass, velocity

    def simulate_mission(self):
        """Полная симуляция миссии"""
        try:
            # Фаза 1: Запуск
            mass_after_launch, v_launch, alt_launch = self.calculate_launch_phase()

            # Фаза 2: Перелет
            mass_after_transfer, v_transfer, r_transfer = self.calculate_transfer_phase(
                mass_after_launch, v_launch
            )

            # Фаза 3: Посадка
            mass_after_landing, v_landing = self.calculate_landing_phase(
                mass_after_transfer, v_transfer
            )

            # Статистика
            stats = MissionStats(
                total_time=self.trajectory[-1].time,
                delta_v=self.calculate_delta_v(),
                fuel_consumed=self.request.initial_mass - mass_after_landing,
                max_acceleration=self.calculate_max_acceleration(),
                arrival_velocity=v_landing
            )

            return MarsMissionResponse(
                success=True,
                trajectory=self.trajectory,
                stats=stats,
                planetary_positions=self.get_planetary_positions()
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка симуляции: {str(e)}")

    def calculate_delta_v(self):
        """Рассчитать общее изменение скорости"""
        return sum(abs(self.trajectory[i].velocity - self.trajectory[i - 1].velocity)
                   for i in range(1, len(self.trajectory)))

    def calculate_max_acceleration(self):
        """Найти максимальное ускорение"""
        max_accel = 0
        for i in range(1, len(self.trajectory)):
            dv = self.trajectory[i].velocity - self.trajectory[i - 1].velocity
            dt = self.trajectory[i].time - self.trajectory[i - 1].time
            if dt > 0:
                accel = abs(dv / dt)
                max_accel = max(max_accel, accel)
        return max_accel

    def get_planetary_positions(self):
        """Получить позиции планет"""
        return {
            "earth": [1.0 * AU, 0],
            "mars": [1.524 * AU, math.pi / 4],  # примерное положение
            "sun": [0, 0]
        }


@router.get("/", response_class=HTMLResponse)
async def mars_mission_page(request: Request):
    return templates.TemplateResponse("physics/M3.html", {"request": request})


@router.post("/simulate", response_model=MarsMissionResponse)
async def simulate_mars_mission(request: MarsMissionRequest):
    """Запустить симуляцию миссии на Марс"""
    try:
        simulator = MarsMissionSimulator(request)
        return simulator.simulate_mission()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
