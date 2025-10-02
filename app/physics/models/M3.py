from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from app.core.fastapi_config import templates
import math
from datetime import datetime, timedelta

router = APIRouter(prefix='/physics/M3')


class MissionFailException(RuntimeError):
    def __init__(self, *args):
        super().__init__(*args)


class MissionPhase(str, Enum):
    LAUNCH = "launch"
    TRANSFER = "transfer"
    LANDING = "landing"


class MarsMissionRequest(BaseModel):
    # Параметры запуска
    initial_mass: float = 1000000  # кг
    gases_velocity: float = 1000000
    velocity: float = 350

    # Параметры перелета
    departure_date: str = "2024-01-01"

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
    fuel_consumption: float
    overload: float


class MissionStats(BaseModel):
    total_time: float
    fuel_consumed: float
    arrival_velocity: float
    mars_start_pos: List[float]


class MarsMissionResponse(BaseModel):
    success: bool
    trajectory: List[TrajectoryPoint]
    stats: MissionStats
    planetary_positions: Dict[str, List[float]]
    message: str = str()


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
        dt = 0.5  # шаг времени в секундах

        mass = self.request.initial_mass
        gases_velocity = self.request.gases_velocity
        target_velocity = self.request.velocity

        t = 0
        altitude = 0
        velocity = 0
        dm_dt = mass * 0.05  # Начальный отрыв
        phase = MissionPhase.LAUNCH

        # Параметры атмосферы (если включено)
        rho0 = 1.225 if self.request.include_atmosphere else 0
        atmosphere_height = 100_000
        height_per_decrease_density = 8_500

        max_altitude = 400_000

        while altitude < max_altitude:  # до высоты 200 км
            if mass <= self.request.landing_mass or velocity < 0:
                raise MissionFailException("Недостаточно топлива для взлёта с Земли")

            # Гравитация
            g = G * M_EARTH / (R_EARTH + altitude) ** 2

            # Сопротивление атмосферы (если включено)
            if self.request.include_atmosphere and altitude < atmosphere_height:
                rho = rho0 * math.exp(-altitude / height_per_decrease_density)
                drag = 0.5 * rho * min(velocity, target_velocity) ** 2 * 0.3  # Cd * A примерно
            else:
                drag = 0

            if velocity < target_velocity:
                acceleration = (dm_dt * dt * gases_velocity - mass * g - drag) / mass
                velocity += acceleration * dt
                dm_dt = mass * acceleration / gases_velocity
            else:
                acceleration = (mass * g + drag) / mass
                dm_dt = mass * acceleration / gases_velocity

            altitude += min(velocity, target_velocity) * dt
            t += dt
            mass -= dm_dt * dt

            self.trajectory.append(TrajectoryPoint(
                x=0, y=altitude, z=0,
                time=t, velocity=target_velocity,
                mass=mass, phase=phase, fuel_consumption=dm_dt,
                overload=acceleration
            ))

        return mass, target_velocity, altitude

    def calculate_transfer_phase(self, initial_mass: float, initial_velocity: float):
        """Фаза 2: Перелет Земля-Марс по эллиптической орбите"""
        dt = 3600  # шаг времени в час
        start_t = self.trajectory[-1].time if self.trajectory else 0
        gases_velocity = self.request.gases_velocity
        t = start_t
        phase = MissionPhase.TRANSFER

        # Орбитальные параметры (круговые орбиты)
        r_earth = 1.0 * AU  # радиус орбиты Земли
        r_mars = 1.524 * AU  # радиус орбиты Марса
        v_earth = 29.78e3  # орбитальная скорость Земли
        v_mars = 24.07e3  # орбитальная скорость Марса

        # Начальные условия для эллиптической орбиты КА
        # Перигелий (ближайшая к Солнцу точка) = орбита Земли
        r_peri = r_earth
        # Афелий (дальняя от Солнца точка) = орбита Марса
        r_apo = r_mars

        # Параметры эллипса
        a = (r_peri + r_apo) / 2  # большая полуось
        e = (r_apo - r_peri) / (r_apo + r_peri)  # эксцентриситет
        b = a * math.sqrt(1 - e ** 2)  # малая полуось

        # Необходимая скорость в перигелии для эллиптической орбиты
        v_peri_needed = math.sqrt(G * M_SUN * (2 / r_peri - 1 / a))

        # РАСЧЕТ РАСХОДА ТОПЛИВА ДЛЯ РАЗГОНА
        # Начальная скорость КА после взлета (относительно Земли)
        v_relative_earth = initial_velocity

        # Скорость КА относительно Солнца после выхода с орбиты Земли
        v_initial_sun = v_earth + v_relative_earth

        # Необходимый прирост скорости для выхода на эллиптическую орбиту
        delta_v_needed = v_peri_needed - v_initial_sun

        if delta_v_needed > 0:
            # Расчет расхода топлива по формуле Циолковского
            mass_after_burn = initial_mass * math.exp(-delta_v_needed / gases_velocity)
            fuel_consumed = initial_mass - mass_after_burn

            # Проверка достаточности топлива
            if mass_after_burn < self.request.landing_mass:
                raise MissionFailException("Недостаточно топлива для выхода на переходную орбиту")

            mass = mass_after_burn
            # print(f"Расход топлива для разгона: {fuel_consumed:.0f} кг")
            # print(f"Масса после разгона: {mass:.0f} кг")
            # print(f"ΔV необходимо: {delta_v_needed:.2f} м/с")
        else:
            fuel_consumed = 0
            mass = initial_mass
            # print("Дополнительный разгон не требуется")

        # Угловые положения планет
        # Земля в верхней точке (π/2) в момент старта
        theta_earth_start = math.pi / 2
        # Марс в нижней точке (3π/2) в момент прибытия
        theta_mars_arrival = 3 * math.pi / 2

        # Время перелета по эллипсу (половина периода)
        transfer_time = math.pi * math.sqrt(a ** 3 / (G * M_SUN))  # время перелета от Земли к Марсу

        # Угловая скорость Марса
        omega_mars = v_mars / r_mars

        # Угол Марса в момент старта
        theta_mars_start = theta_mars_arrival - omega_mars * transfer_time

        # Начальные условия
        # старт с позиции Земли с орбитальной скоростью + дополнительная
        x = r_earth * math.cos(theta_earth_start)
        y = r_earth * math.sin(theta_earth_start)

        # Начальная скорость (касательная к орбите)
        vx = -v_peri_needed * math.sin(theta_earth_start)
        vy = v_peri_needed * math.cos(theta_earth_start)

        current_time = 0

        # Моделирование движения по эллипсу
        while current_time < transfer_time:
            # Текущее расстояние до Солнца
            r = math.sqrt(x ** 2 + y ** 2)

            # Угловая позиция
            theta = math.atan2(y, x)

            # Гравитация Солнца
            a_sun = -G * M_SUN / r ** 2
            ax = a_sun * math.cos(theta)
            ay = a_sun * math.sin(theta)

            # Интегрирование (упрощенное)
            vx += ax * dt
            vy += ay * dt
            x += vx * dt
            y += vy * dt

            t += dt
            current_time += dt

            self.trajectory.append(TrajectoryPoint(
                x=x, y=y, z=0,
                time=t, velocity=math.sqrt(vx ** 2 + vy ** 2),
                mass=mass, phase=phase, fuel_consumption=fuel_consumed,
                overload=math.sqrt(ax ** 2 + ay ** 2)
            ))

        # Финальные параметры
        final_r = math.sqrt(x ** 2 + y ** 2)
        final_v = math.sqrt(vx ** 2 + vy ** 2) - v_mars

        # Позиция Марса в момент старта
        mars_start_pos = [
            r_mars * math.cos(theta_mars_start),
            r_mars * math.sin(theta_mars_start)
        ]

        return mass, final_v, final_r, mars_start_pos

    def calculate_landing_phase(self, initial_mass: float, approach_velocity: float):
        """Фаза 3: Посадка на Марс"""
        dt = 5  # маленький шаг времени
        t = self.trajectory[-1].time if self.trajectory else 0
        gases_velocity = self.request.gases_velocity
        phase = MissionPhase.LANDING

        altitude = 200_000  # начальная высота
        velocity = approach_velocity
        mass = initial_mass
        min_velocity = 4.
        max_velocity = 10.

        rho0 = 0.025 if self.request.include_atmosphere else 0
        atmosphere_height = 100_000
        height_per_decrease_density = 8_500
        dm_dt = mass * 0.05

        while altitude > 0:
            # Гравитация Марса
            g = G * M_MARS / (R_MARS + altitude) ** 2

            # Сопротивление атмосферы (если включено)
            if self.request.include_atmosphere and altitude < atmosphere_height:
                rho = rho0 * math.exp(-altitude / height_per_decrease_density)
                drag = 0.5 * rho * velocity ** 2 * 0.3  # Cd * A примерно
            else:
                drag = 0

            if mass < self.request.landing_mass or velocity <= min_velocity:
                acceleration = (mass * g + drag) / mass
                dm_dt = 0
            else:
                acceleration = (dm_dt * dt * gases_velocity - mass * g - drag) / mass
                dm_dt = -mass * acceleration / gases_velocity

            velocity += acceleration * dt
            altitude -= velocity * dt
            t += dt
            dt *= 0.99999
            mass -= dm_dt * dt

            if t - self.trajectory[-1].time > 5:
                self.trajectory.append(TrajectoryPoint(
                    x=0, y=altitude, z=0,
                    time=t, velocity=velocity,
                    mass=mass, phase=phase, fuel_consumption=dm_dt,
                    overload=acceleration
                ))

        self.trajectory.append(TrajectoryPoint(
            x=0, y=0, z=0,
            time=t, velocity=0,
            mass=mass, phase=phase, fuel_consumption=0,
            overload=0
        ))

        if velocity > max_velocity * 4:
            raise MissionFailException("Корабль разбился при посадке")

        if velocity > max_velocity:
            raise MissionFailException("Корабль серьёзно пострадал при посадке")

        return mass, velocity

    def simulate_mission(self):
        """Полная симуляция миссии"""
        try:
            # Фаза 1: Запуск
            mass_after_launch, v_launch, alt_launch = self.calculate_launch_phase()

            # Фаза 2: Перелет
            mass_after_transfer, v_transfer, r_transfer, mars_start_pos = self.calculate_transfer_phase(
                mass_after_launch, v_launch
            )

            # Фаза 3: Посадка
            mass_after_landing, v_landing = self.calculate_landing_phase(
                mass_after_transfer, v_transfer
            )

            # Статистика
            stats = MissionStats(
                total_time=self.trajectory[-1].time,
                fuel_consumed=self.request.initial_mass - mass_after_landing,
                arrival_velocity=v_landing,
                mars_start_pos=mars_start_pos
            )

            return MarsMissionResponse(
                success=True,
                trajectory=self.trajectory,
                stats=stats,
                planetary_positions=self.get_planetary_positions()
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка симуляции: {str(e)}")

    def get_planetary_positions(self):
        """Получить позиции планет"""
        return {
            "earth": [1.0 * AU, 0],
            "mars": [1.524 * AU, math.pi * 3 / 2],  # примерное положение
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
