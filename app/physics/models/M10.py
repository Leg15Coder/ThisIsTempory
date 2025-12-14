from dataclasses import dataclass
from typing import Tuple
from fastapi import Request, HTTPException, APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List
import numpy as np
from app.core.fastapi_config import templates

router = APIRouter(prefix="/physics/M10")
simulator = None


class SimulationRequest(BaseModel):
    temperature_K: float = 300.0
    field_angle: float = 0.0
    field_strength_T: float = 0.0
    cube_size: int = 8
    num_steps: int = 1


class SpinSnapshot(BaseModel):
    up_count: List[List[int]]
    down_count: List[List[int]]
    directions: List[List[float]]
    energy: float
    magnetization: float
    temperature: float
    field: float


class SimulationResponse(BaseModel):
    success: bool
    snapshot: SpinSnapshot
    message: str = ""


@dataclass
class SpinState:
    spins: np.ndarray
    energy: float
    magnetization: float
    temperature: float
    field_angle: float
    field_strength: float


class Spin3DSimulator:
    def __init__(self, size: int = 8):
        self.size = max(1, int(size))
        self.rng = np.random.default_rng()
        self.spins = self.rng.choice([-1, 1], size=(self.size, self.size, self.size))
        self.temperature_K = 300.0
        self.field_strength_T = 0.0
        self.field_angle = 0.0
        self.coupling = 1.0
        self.alpha = 1.0
        self.beta = 8.0
        self.mc_steps = max(1, self.size)

        self.K_B = 1.380649e-23
        self.ENERGY_SCALE = 1.0

        self.energy = 0.0
        self.neighbour_energy = 0.0

        self.up_count = np.sum(self.spins > 0, axis=2)
        self.down_count = np.sum(self.spins < 0, axis=2)
        self.mean_spin_map = (self.up_count - self.down_count) / float(self.size)

        self.calculate_energy()

    @staticmethod
    def temperature_to_normalized(T_K: float) -> float:
        return max(0.01, T_K / 300.0)

    @staticmethod
    def field_to_normalized(B_T: float) -> float:
        return B_T / 20.0

    def get_field_components(self) -> Tuple[float, float]:
        B_normalized = self.field_to_normalized(self.field_strength_T)
        return 0.0, B_normalized

    def calculate_energy(self) -> float:
        s = self.spins
        neigh = (
            np.roll(s, 1, axis=0) + np.roll(s, -1, axis=0) +
            np.roll(s, 1, axis=1) + np.roll(s, -1, axis=1) +
            np.roll(s, 1, axis=2) + np.roll(s, -1, axis=2)
        )
        self.neighbour_energy = -0.5 * self.coupling * float(np.sum(s * neigh))
        self.energy = -0.5 * float(np.sum(s))
        return self.energy

    def calculate_magnetization(self) -> float:
        return float(np.mean(self.spins))

    def metropolis_step(self) -> int:
        accepted = 0
        _, By = self.get_field_components()
        T_norm = self.temperature_to_normalized(self.temperature_K)

        for _ in range(self.mc_steps):
            i = int(self.rng.integers(0, self.size))
            j = int(self.rng.integers(0, self.size))
            k = int(self.rng.integers(0, self.size))
            s = self.spins[i, j, k]

            neighbors = (
                self.spins[(i+1) % self.size, j, k] +
                self.spins[(i-1) % self.size, j, k] +
                self.spins[i, (j+1) % self.size, k] +
                self.spins[i, (j-1) % self.size, k] +
                self.spins[i, j, (k+1) % self.size] +
                self.spins[i, j, (k-1) % self.size]
            )

            E_old = -self.coupling * s * neighbors - s * By
            E_new = -self.coupling * (-s) * neighbors - (-s) * By
            dE = E_new - E_old

            if dE < 0 or self.rng.random() < self.alpha * np.exp(-dE / (T_norm + 1e-12)):
                self.spins[i, j, k] = -s
                delta_neigh = -0.5 * self.coupling * ((-s) - s) * neighbors
                self.neighbour_energy += float(delta_neigh)
                self.energy += 2 * (-s)
                accepted += 1

                if s > 0:
                    self.up_count[i, j] -= 1
                    self.down_count[i, j] += 1
                else:
                    self.up_count[i, j] += 1
                    self.down_count[i, j] -= 1

                self.mean_spin_map[i, j] = (self.up_count[i, j] - self.down_count[i, j]) / float(self.size)

        return accepted

    def step(self) -> dict:
        T_norm = self.temperature_to_normalized(self.temperature_K)
        num_mc_updates = max(1, int(T_norm * self.beta))

        if self.size >= 100:
            num_mc_updates = max(1, num_mc_updates // 4)

        for _ in range(num_mc_updates):
            self.metropolis_step()

        if self.size < 100:
            self.calculate_energy()

        magnetization = float(np.mean(self.spins))

        return {
            'energy': self.get_energy(),
            'magnetization': magnetization,
            'temperature': self.temperature_K,
            'field': self.field_strength_T
        }

    def set_temperature(self, T_K: float):
        self.temperature_K = max(0.0, float(T_K))

    def get_energy(self):
        Bx, By = self.get_field_components()
        return self.energy * (Bx + By) / 2 + self.neighbour_energy

    def set_field(self, angle: float, strength_T: float):
        self.field_angle = 0.0
        self.field_strength_T = float(strength_T)

    def get_2d_layer(self, z: int = None) -> np.ndarray:
        if z is None:
            return np.mean(self.spins, axis=2)
        else:
            z = z % self.size
            return self.spins[:, :, z]

    def get_magnetization_map(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.up_count, self.down_count

    def get_direction_map(self) -> np.ndarray:
        total_angle = (self.field_angle + self.mean_spin_map * 90.0) % 360.0
        angles = np.radians(total_angle)
        return angles


@router.get("/", response_class=HTMLResponse)
async def get_spin_page(request: Request):
    try:
        return templates.TemplateResponse("physics/M10.html", {"request": request})
    except Exception as e:
        return HTMLResponse(
            f"""
            <h1>Ошибка</h1>
            <p>Страница не найдена</p>
            <p>Подробности: {str(e)}</p>
            <a href="/physics/M10/spin">Попробовать рабочую страницу</a>
            """,
            status_code=404
        )


@router.get("/spin", response_class=HTMLResponse)
async def spin_page(request: Request):
    try:
        return templates.TemplateResponse("physics/M10.html", {"request": request})
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {str(e)}</h1>", status_code=500)


@router.post("/step", response_model=SimulationResponse)
async def single_step(request: SimulationRequest):
    global simulator

    try:
        if simulator is None or simulator.size != request.cube_size:
            simulator = Spin3DSimulator(size=request.cube_size)

        simulator.set_temperature(request.temperature_K)
        simulator.set_field(request.field_angle, request.field_strength_T)

        stats = simulator.step()

        up_counts, down_counts = simulator.get_magnetization_map()
        directions = simulator.get_direction_map()

        snapshot = SpinSnapshot(
            up_count=up_counts.tolist(),
            down_count=down_counts.tolist(),
            directions=directions.tolist(),
            energy=stats['energy'],
            magnetization=stats['magnetization'],
            temperature=stats['temperature'],
            field=stats['field']
        )

        return SimulationResponse(
            success=True,
            snapshot=snapshot,
            message="Step completed"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_simulation(request: SimulationRequest):
    global simulator
    simulator = Spin3DSimulator(size=request.cube_size)
    simulator.set_temperature(request.temperature_K)
    simulator.set_field(request.field_angle, request.field_strength_T)

    return {"success": True, "message": "Simulation reset"}
