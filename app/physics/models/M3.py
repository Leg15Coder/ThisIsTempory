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


class MarsMissionRequest(BaseModel):  # В СИ
    initial_mass: float = 1000000
    gases_velocity: float = 1000000
    velocity: float = 350
    landing_velocity: float = 350
    landing_mass: float = 10000
    include_atmosphere: bool = False
    bounded_overload: bool = False


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


G = 6.67430e-11  # гравитационная постоянная
g0 = 9.81
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
        dt = 0.5

        mass = self.request.initial_mass
        gases_velocity = self.request.gases_velocity
        target_velocity = self.request.velocity
        phase = MissionPhase.LAUNCH

        t = 0
        altitude = 0
        velocity = 0

        rho0 = 1.225 if self.request.include_atmosphere else 0
        atmosphere_height = 100_000
        height_per_decrease_density = 8_500

        max_altitude = R_EARTH

        while altitude < max_altitude:
            if mass <= self.request.landing_mass or altitude < 0:
                raise MissionFailException("Недостаточно топлива для взлёта с Земли")

            g = G * M_EARTH / (R_EARTH + altitude) ** 2

            if self.request.include_atmosphere and altitude <= atmosphere_height:
                rho = rho0 * math.exp(-altitude / height_per_decrease_density)
                drag = 0.5 * rho * velocity ** 2 * 0.3  # Примерно
            else:
                drag = 0

            if velocity < target_velocity:
                required_acceleration = (target_velocity - velocity) / dt
                required_thrust = mass * (required_acceleration + g) + drag

                max_possible_thrust = mass * 0.1 * gases_velocity if not self.request.bounded_overload else 11 * g0 * mass

                actual_thrust = min(required_thrust, max_possible_thrust)
                dm_dt = actual_thrust / gases_velocity

                acceleration = (dm_dt * gases_velocity - mass * g - drag) / mass
                velocity += acceleration * dt
            else:
                acceleration = (mass * g + drag) / mass
                dm_dt = mass * acceleration / gases_velocity
                acceleration = 0

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
        dt = 3600
        start_t = self.trajectory[-1].time if self.trajectory else 0
        gases_velocity = self.request.gases_velocity
        t = start_t
        phase = MissionPhase.TRANSFER

        r_earth = 1.0 * AU
        r_mars = 1.524 * AU
        v_earth = 29.78e3
        v_mars = 24.07e3

        r_peri = r_earth
        r_apo = r_mars

        a = (r_peri + r_apo) / 2
        e = (r_apo - r_peri) / (r_apo + r_peri)
        b = a * math.sqrt(1 - e ** 2)

        v_peri_needed = math.sqrt(G * M_SUN * (2 / r_peri - 1 / a))

        v_relative_earth = initial_velocity

        v_initial_sun = v_earth + v_relative_earth

        delta_v_needed = v_peri_needed - v_initial_sun

        if delta_v_needed > 0:
            mass_after_burn = initial_mass * math.exp(-delta_v_needed / gases_velocity)
            fuel_consumed = initial_mass - mass_after_burn

            if mass_after_burn < self.request.landing_mass:
                raise MissionFailException("Недостаточно топлива для выхода на переходную орбиту")

            mass = mass_after_burn
        else:
            fuel_consumed = 0
            mass = initial_mass

        theta_earth_start = math.pi / 2
        theta_mars_arrival = 3 * math.pi / 2

        transfer_time = math.pi * math.sqrt(a ** 3 / (G * M_SUN))

        omega_mars = v_mars / r_mars

        theta_mars_start = theta_mars_arrival - omega_mars * transfer_time

        x = r_earth * math.cos(theta_earth_start)
        y = r_earth * math.sin(theta_earth_start)

        vx = -v_peri_needed * math.sin(theta_earth_start)
        vy = v_peri_needed * math.cos(theta_earth_start)

        current_time = 0

        while current_time < transfer_time:
            r = math.sqrt(x ** 2 + y ** 2)

            theta = math.atan2(y, x)

            a_sun = -G * M_SUN / r ** 2
            ax = a_sun * math.cos(theta)
            ay = a_sun * math.sin(theta)

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

        final_r = math.sqrt(x ** 2 + y ** 2)
        final_v = math.sqrt(vx ** 2 + vy ** 2) - v_mars

        mars_start_pos = [
            r_mars * math.cos(theta_mars_start),
            r_mars * math.sin(theta_mars_start)
        ]

        return mass, final_v, final_r, mars_start_pos

    def calculate_landing_phase(self, initial_mass: float, approach_velocity: float):
        dt = .5
        t = self.trajectory[-1].time if self.trajectory else 0
        gases_velocity = self.request.gases_velocity
        phase = MissionPhase.LANDING

        altitude = 12 * R_MARS
        velocity = approach_velocity
        mass = initial_mass
        min_velocity = self.request.landing_velocity
        max_velocity = .8

        rho0 = 0.025 if self.request.include_atmosphere else 0
        atmosphere_height = 100_000
        height_per_decrease_density = 8_500

        loc_dt = 1
        loc_velocity = 0
        while altitude > 2 * atmosphere_height:
            g = G * M_MARS / (R_MARS + altitude) ** 2
            loc_velocity += g * loc_dt
            altitude -= loc_velocity * loc_dt

        engine_start_altitude = self.calculate_engine_start_altitude(
            velocity, mass, gases_velocity, min_velocity
        )

        while altitude > 0:
            g = G * M_MARS / (R_MARS + altitude) ** 2

            if self.request.include_atmosphere and altitude < atmosphere_height:
                rho = rho0 * math.exp(-altitude / height_per_decrease_density)
                drag = 0.5 * rho * velocity ** 2 * 0.3  # Примерно
            else:
                drag = 0

            if (mass < self.request.landing_mass or
                    velocity <= min_velocity and altitude > engine_start_altitude or
                    velocity < max_velocity and altitude <= engine_start_altitude):
                acceleration = (mass * g + drag) / mass
                dm_dt = 0
            else:
                target_velocity = min_velocity if altitude > engine_start_altitude else max_velocity

                required_acceleration = -(target_velocity - velocity) / dt
                required_thrust = mass * (required_acceleration + g) + drag

                max_possible_thrust = mass * 0.1 * gases_velocity if not self.request.bounded_overload else 11 * g0 * mass

                actual_thrust = min(required_thrust, max_possible_thrust)
                dm_dt = actual_thrust / gases_velocity

                acceleration = -(dm_dt * gases_velocity - mass * g - drag) / mass

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

        if velocity > max_velocity * 64:
            raise MissionFailException("Корабль разбился при посадке")

        if velocity > max_velocity * 16:
            raise MissionFailException("Корабль серьёзно пострадал при посадке")

        return mass, velocity

    def calculate_engine_start_altitude(self, velocity: float, mass: float, gases_velocity: float, min_velocity: float):
        max_thrust = mass * 0.1 * gases_velocity if not self.request.bounded_overload else 11 * g0 * mass
        max_acceleration = max_thrust / mass

        g_surface = G * M_MARS / R_MARS ** 2

        effective_acceleration = max_acceleration - g_surface

        required_height = (velocity ** 2 - min_velocity ** 2) / (2 * effective_acceleration)

        safety_margin = 1.2

        return required_height * safety_margin

    def simulate_mission(self):
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
    try:
        simulator = MarsMissionSimulator(request)
        return simulator.simulate_mission()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
