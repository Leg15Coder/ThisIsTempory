import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import numpy as np
from scipy import linalg
from typing import Tuple, List, Dict, Optional
import logging
import warnings
import math

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field, model_validator
from app.core.fastapi_config import templates


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/M21", tags=["Physics M21"])

EPSILON_0 = 8.854187817e-12  # Ф/м


class SphereElement:
    def __init__(self, center: np.ndarray, area: float, sphere_id: int):
        self.center = center
        self.area = area
        self.sphere_id = sphere_id
        self.charge_density = 0.0


class ElectrostaticsRequest(BaseModel):
    mode: str = Field("separated", description="Режим: separated | concentric | plates")
    R1: float = Field(..., gt=0, le=1.0, description="Радиус первой сферы / полуразмер пластины (м)")
    R2: float = Field(..., gt=0, le=1.0, description="Радиус второй сферы / полуразмер пластины (м)")
    d: float = Field(..., ge=0, le=10.0, description="Расстояние между центрами (м)")
    V: float = Field(..., gt=0, le=1000, description="Разность потенциалов (В)")
    n_divisions: int = Field(10, ge=3, le=100, description="Количество делений сетки")

    @model_validator(mode='after')
    def validate_distance(self) -> 'ElectrostaticsRequest':
        mode = self.mode
        r1, r2, d = self.R1, self.R2, self.d
        if mode == 'separated':
            if d <= r1 + r2:
                raise ValueError(
                    f'Расстояние d должно быть больше суммы радиусов ({r1 + r2:.3f} м)'
                )
        elif mode == 'concentric':
            if abs(r1 - r2) < 1e-6:
                raise ValueError('Радиусы вложенных сфер должны различаться')
            rmin, rmax = min(r1, r2), max(r1, r2)
            if d + rmin >= rmax:
                raise ValueError('Для вложенных сфер требуется d + min(r1,r2) < max(r1,r2)')
        elif mode == 'plates' and d <= 0:
            raise ValueError('Расстояние между пластинами d должно быть > 0')
        return self



class ElectrostaticsResponse(BaseModel):
    success: bool
    mode: str
    Q1: float
    Q2: float
    C_numerical: float
    C_analytical: float
    n_elements: int
    field_img: str
    error: Optional[str] = None


def generate_sphere_mesh(radius: float, center: np.ndarray, n_divisions: int, sphere_id: int = 0) -> List[SphereElement]:
    elements = []
    theta_values = np.linspace(0, np.pi, n_divisions + 1)
    phi_values = np.linspace(0, 2 * np.pi, n_divisions + 1)

    for i in range(n_divisions):
        for j in range(n_divisions):
            theta1, theta2 = theta_values[i], theta_values[i + 1]
            phi1, phi2 = phi_values[j], phi_values[j + 1]
            theta_mid = (theta1 + theta2) / 2
            phi_mid = (phi1 + phi2) / 2

            x = center[0] + radius * np.sin(theta_mid) * np.cos(phi_mid)
            y = center[1] + radius * np.sin(theta_mid) * np.sin(phi_mid)
            z = center[2] + radius * np.cos(theta_mid)

            area = radius ** 2 * (phi2 - phi1) * (np.cos(theta1) - np.cos(theta2))
            elem = SphereElement(np.array([x, y, z]), abs(area), sphere_id)
            elements.append(elem)
    return elements


def generate_plate_mesh(half_size: float, z_center: float, n_divisions: int, sphere_id: int = 0) -> List[SphereElement]:
    elements = []
    coords = np.linspace(-half_size, half_size, n_divisions + 1)
    dx = coords[1] - coords[0]
    area = dx ** 2

    for i in range(n_divisions):
        for j in range(n_divisions):
            x = (coords[i] + coords[i + 1]) / 2
            y = (coords[j] + coords[j + 1]) / 2
            elem = SphereElement(np.array([x, y, z_center]), area, sphere_id)
            elements.append(elem)
    return elements


def calculate_potential_matrix(elements: List[SphereElement]) -> np.ndarray:
    centers = np.array([e.center for e in elements])
    areas = np.array([e.area for e in elements])

    diff = centers[:, None, :] - centers[None, :, :]
    r_mat = np.linalg.norm(diff, axis=2)

    with np.errstate(divide='ignore', invalid='ignore'):
        A = np.where(r_mat > 0, 1.0 / (4 * np.pi * EPSILON_0 * r_mat), 0.0)

    r_equiv = np.sqrt(areas / np.pi)
    np.fill_diagonal(A, 1.0 / (4 * np.pi * EPSILON_0 * r_equiv))
    return A


def calculate_field_on_plane(
    result: Dict,
    plane: str = 'xy',
    z_coord: float = 0.0,
    grid_size: int = 50,
    extent: float = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:

    elements = result['elements']
    charges = result['charges']
    mode = result.get('mode', 'separated')

    if extent is None:
        if mode == 'plates':
            half = max(result['R1'], result['R2'])
            extent = half * 3 + result['d'] * 2
        else:
            extent = result['d'] + max(result['R1'], result['R2']) * 3.2

    if plane == 'xy':
        xs = np.linspace(-extent / 3, result['d'] + extent / 3, grid_size)
        ys = np.linspace(-extent / 2, extent / 2, grid_size)
        X, Y = np.meshgrid(xs, ys)
        Z = np.full_like(X, z_coord)
    elif plane == 'xz':
        xs = np.linspace(-extent / 3, result['d'] + extent / 3, grid_size)
        zs = np.linspace(-extent / 2, extent / 2, grid_size)
        X, Z = np.meshgrid(xs, zs)
        Y = np.full_like(X, z_coord)
    else:
        ys = np.linspace(-extent / 2, extent / 2, grid_size)
        zs = np.linspace(-extent / 2, extent / 2, grid_size)
        Y, Z = np.meshgrid(ys, zs)
        X = np.full_like(Y, z_coord)

    centers = np.array([e.center for e in elements])
    q = np.array(charges)

    center_by_id = {}
    for sid in (0, 1):
        pts = np.array([e.center for e in elements if e.sphere_id == sid])
        center_by_id[sid] = pts.mean(axis=0) if pts.size else np.array([0.0, 0.0, 0.0])

    rx = X[None] - centers[:, 0, None, None]
    ry = Y[None] - centers[:, 1, None, None]
    rz = Z[None] - centers[:, 2, None, None]
    r3 = (rx ** 2 + ry ** 2 + rz ** 2) ** 1.5

    mask = r3 > 1e-30
    k = q[:, None, None] / (4 * np.pi * EPSILON_0)

    Ex = np.sum(np.where(mask, k * rx / r3, 0.0), axis=0)
    Ey = np.sum(np.where(mask, k * ry / r3, 0.0), axis=0)
    Ez = np.sum(np.where(mask, k * rz / r3, 0.0), axis=0)

    if mode == 'separated':
        c0 = center_by_id.get(0, np.array([0.0, 0.0, 0.0]))
        c1 = center_by_id.get(1, np.array([0.0, 0.0, 0.0]))
        r0 = result.get('R1', 0.0)
        r1 = result.get('R2', 0.0)
        if plane == 'xy':
            inside0 = (X - c0[0]) ** 2 + (Y - c0[1]) ** 2 < r0 ** 2
            inside1 = (X - c1[0]) ** 2 + (Y - c1[1]) ** 2 < r1 ** 2
        elif plane == 'xz':
            inside0 = (X - c0[0]) ** 2 + (Z - c0[2]) ** 2 < r0 ** 2
            inside1 = (X - c1[0]) ** 2 + (Z - c1[2]) ** 2 < r1 ** 2
        else:
            inside0 = (Y - c0[1]) ** 2 + (Z - c0[2]) ** 2 < r0 ** 2
            inside1 = (Y - c1[1]) ** 2 + (Z - c1[2]) ** 2 < r1 ** 2
        inside_mask = inside0 | inside1
        Ex = np.where(inside_mask, 0.0, Ex)
        Ey = np.where(inside_mask, 0.0, Ey)
        Ez = np.where(inside_mask, 0.0, Ez)

    if mode == 'concentric':
        r1, r2 = result['R1'], result['R2']
        if r1 <= r2:
            inner_r, outer_r = r1, r2
            inner_c = center_by_id[0]
            outer_c = center_by_id[1]
        else:
            inner_r, outer_r = r2, r1
            inner_c = center_by_id[1]
            outer_c = center_by_id[0]

        if plane == 'xy':
            dx_i = X - inner_c[0]; dy_i = Y - inner_c[1]
            dx_o = X - outer_c[0]; dy_o = Y - outer_c[1]
            r2_inner = dx_i ** 2 + dy_i ** 2
            r2_outer = dx_o ** 2 + dy_o ** 2
            mask_zero = (r2_inner < inner_r ** 2) | (r2_outer > outer_r ** 2)
            Ex = np.where(mask_zero, 0.0, Ex)
            Ey = np.where(mask_zero, 0.0, Ey)
        elif plane == 'xz':
            dx_i = X - inner_c[0]; dz_i = Z - inner_c[2]
            dx_o = X - outer_c[0]; dz_o = Z - outer_c[2]
            r2_inner = dx_i ** 2 + dz_i ** 2
            r2_outer = dx_o ** 2 + dz_o ** 2
            mask_zero = (r2_inner < inner_r ** 2) | (r2_outer > outer_r ** 2)
            Ex = np.where(mask_zero, 0.0, Ex)
            Ez = np.where(mask_zero, 0.0, Ez)
        else:
            dy_i = Y - inner_c[1]; dz_i = Z - inner_c[2]
            dy_o = Y - outer_c[1]; dz_o = Z - outer_c[2]
            r2_inner = dy_i ** 2 + dz_i ** 2
            r2_outer = dy_o ** 2 + dz_o ** 2
            mask_zero = (r2_inner < inner_r ** 2) | (r2_outer > outer_r ** 2)
            Ey = np.where(mask_zero, 0.0, Ey)
            Ez = np.where(mask_zero, 0.0, Ez)

    if plane == 'xy':
        return X, Y, Ex, Ey
    elif plane == 'xz':
        return X, Z, Ex, Ez
    else:
        return Y, Z, Ey, Ez


def solve_electrostatics(
    R1: float, R2: float, d: float, V: float, n_divisions: int = 10, mode: str = 'separated'
) -> Dict:
    logger.info(f"Расчёт: mode={mode}, R1={R1}, R2={R2}, d={d}, V={V}, n={n_divisions}")

    if mode == 'separated':
        if d <= R1 + R2:
            raise ValueError("Сферы пересекаются! Увеличьте расстояние d")

        center1 = np.array([0.0, 0.0, 0.0])
        center2 = np.array([d,   0.0, 0.0])
        elements1 = generate_sphere_mesh(R1, center1, n_divisions, sphere_id=0)
        elements2 = generate_sphere_mesh(R2, center2, n_divisions, sphere_id=1)

    elif mode == 'concentric':
        if abs(R1 - R2) < 1e-6:
            raise ValueError("Радиусы вложенных сфер должны различаться")

        center1 = np.array([0.0, 0.0, 0.0])
        center2 = np.array([d,   0.0, 0.0])
        elements1 = generate_sphere_mesh(R1, center1, n_divisions, sphere_id=0)
        elements2 = generate_sphere_mesh(R2, center2, n_divisions, sphere_id=1)

    elif mode == 'plates':
        if d <= 0:
            raise ValueError("Расстояние между пластинами d должно быть > 0")
        elements1 = generate_plate_mesh(R1, -d / 2, n_divisions, sphere_id=0)
        elements2 = generate_plate_mesh(R2,  d / 2, n_divisions, sphere_id=1)

    else:
        raise ValueError(f"Неизвестный режим: {mode}")

    all_elements = elements1 + elements2
    n_total = len(all_elements)
    logger.info(f"Элементов: {len(elements1)} + {len(elements2)} = {n_total}")

    A = calculate_potential_matrix(all_elements)

    n = len(all_elements)
    M = np.zeros((n + 1, n + 1))
    M[:n, :n] = A
    M[:n, n] = -1.0
    M[n, :n] = 1.0

    b = np.zeros(n + 1)
    b[:n] = np.array([V / 2.0 if e.sphere_id == 0 else -V / 2.0 for e in all_elements])
    b[n] = 0.0

    try:
        cond = np.linalg.cond(M[:n, :n])
    except Exception:
        cond = np.linalg.cond(M)
    M_reg = M.copy()
    if cond > 1e12:
        diag_mean = np.mean(np.abs(np.diag(A))) if np.any(np.diag(A)) else 1.0
        reg = max(1e-16, 1e-9 * diag_mean)
        logger.warning(f"Матрица плохо обусловлена (cond={cond:.3e}), добавляю регуляризацию {reg:.3e}")
        M_reg[:n, :n] += np.eye(n) * reg

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=linalg.LinAlgWarning)
            sol = linalg.solve(M_reg, b)
        q = sol[:n]
    except linalg.LinAlgError as e:
        logger.error(f"Ошибка СЛАУ: {e}")
        raise ValueError("Не удалось решить систему уравнений. Попробуйте другие параметры.")

    for i, elem in enumerate(all_elements):
        elem.charge_density = q[i] / elem.area

    Q1 = float(np.sum(q[[e.sphere_id == 0 for e in all_elements]]))
    Q2 = float(np.sum(q[[e.sphere_id == 1 for e in all_elements]]))

    C_numerical = abs(Q1) / V
    Rmin, Rmax = min(R1, R2), max(R1, R2)

    try:
        if mode == 'concentric':
            C_spherical = 4 * np.pi * EPSILON_0 * Rmin * Rmax / max((Rmax - Rmin), 1e-12) * (1 + d ** 2 * Rmin * Rmax / max((Rmax - Rmin) ** 2, 1e-12) / max((Rmax ** 2 - d ** 2), 1e-12))
        elif mode == 'plates':
            side_min = 2.0 * Rmin
            area_overlap = max(0.0, side_min ** 2)
            C_by_area = EPSILON_0 * area_overlap / max(d, 1e-12)
            a_eq = math.sqrt(max(area_overlap, 0.0) / math.pi) if area_overlap > 0 else 0.0
            fringe = 0.0
            if a_eq > 0 and d > 0:
                arg = 8.0 * a_eq / d
                if arg > 0:
                    fringe = 2.0 * math.pi * EPSILON_0 * a_eq * (math.log(arg) - 1.0)
            C_spherical = max(C_by_area + fringe, 0.0)
        else:
            denom = (1 / Rmin + 1 / Rmax - 2 / d - Rmin * Rmax / d / max((d ** 2 - Rmin ** 2), 1e-12) - Rmin * Rmax / d / max((d ** 2 - Rmax ** 2), 1e-12))
            if abs(denom) < 1e-18:
                raise ZeroDivisionError
            C_spherical = 4 * np.pi * EPSILON_0 / denom
    except (ValueError, ZeroDivisionError, OverflowError):
        if mode == 'plates':
            side_min = 2.0 * Rmin
            area_overlap = max(0.0, side_min ** 2)
            C_spherical = EPSILON_0 * area_overlap / max(d, 1e-12)
        else:
            C_spherical = (4 * np.pi * EPSILON_0 * (Rmin + Rmax) / 2.0)

    logger.info(f"Q1={Q1:.3e} Кл, Q2={Q2:.3e} Кл, C={C_numerical:.3e} Ф")

    return {
        'mode': mode,
        'elements': all_elements,
        'charges': q.tolist(),
        'Q1': Q1, 'Q2': Q2,
        'C_numerical': C_numerical,
        'C_isolated':  C_spherical,
        'n_elements': n_total,
        'R1': R1, 'R2': R2, 'd': d, 'V': V,
    }


def calculate_capacitance_theoretical(R1: float, R2: float, d: Optional[float] = None) -> Dict[str, float]:
    C_isolated_1 = 4 * np.pi * EPSILON_0 * R1
    C_isolated_2 = 4 * np.pi * EPSILON_0 * R2
    Rmin, Rmax = min(R1, R2), max(R1, R2)
    C_spherical = 4 * np.pi * EPSILON_0 * Rmin * Rmax / (Rmax - Rmin) if abs(Rmax - Rmin) > 1e-9 else C_isolated_1
    result: Dict[str, float] = {'C_isolated_1': C_isolated_1, 'C_isolated_2': C_isolated_2, 'C_spherical': C_spherical}
    if d is not None and d > 0:
        side1 = 2.0 * R1
        side2 = 2.0 * R2
        side_overlap = min(side1, side2)
        area_overlap = max(0.0, side_overlap ** 2)
        C_area = EPSILON_0 * area_overlap / d
        a_eq = math.sqrt(area_overlap / math.pi) if area_overlap > 0 else 0.0
        fringe = 0.0
        if a_eq > 0:
            arg = max(8.0 * a_eq / d, 1e-12)
            fringe = 2.0 * math.pi * EPSILON_0 * a_eq * (math.log(arg) - 1.0)
        C_area_with_edge = max(C_area + fringe, 0.0)
        result.update({'plate_area': area_overlap, 'C_area': C_area, 'C_area_with_edge': C_area_with_edge})
    return result


def create_field_visualization(result: Dict) -> str:
    mode = result.get('mode', 'separated')
    R1, R2, d = result['R1'], result['R2'], result['d']

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_facecolor('#0d0d1a')

    if mode == 'plates':
        plane = 'xz'
        grid_size = 60
    elif mode == 'concentric':
        plane = 'xz'
        grid_size = 80
    else:
        plane = 'xy'
        grid_size = 60

    X, Y, Ex, Ey = calculate_field_on_plane(result, plane=plane, z_coord=0.0, grid_size=grid_size)

    E_magnitude = np.sqrt(Ex ** 2 + Ey ** 2)

    E_plot = np.nan_to_num(E_magnitude, nan=0.0, posinf=np.nanmax(E_magnitude[np.isfinite(E_magnitude)]) if np.any(np.isfinite(E_magnitude)) else 0.0)
    try:
        contour = ax.contourf(X, Y, E_plot, levels=30, cmap='plasma', alpha=0.9)
    except Exception:
        contour = ax.pcolormesh(X, Y, E_plot, cmap='plasma', shading='auto')

    elts = result.get('elements', [])
    if elts:
        c0 = np.mean([e.center for e in elts if e.sphere_id == 0], axis=0)
        c1 = np.mean([e.center for e in elts if e.sphere_id == 1], axis=0)
    else:
        c0 = np.array([0.0, 0.0, 0.0]); c1 = np.array([0.0, 0.0, 0.0])

    if mode == 'concentric':
        if R1 <= R2:
            inner_r, outer_r = R1, R2; inner_c, outer_c = c0, c1
        else:
            inner_r, outer_r = R2, R1; inner_c, outer_c = c1, c0
        if plane == 'xz':
            dx_i = X - inner_c[0]; dz_i = Y - inner_c[2]
            dx_o = X - outer_c[0]; dz_o = Y - outer_c[2]
            inside_mask = (dx_i ** 2 + dz_i ** 2) < inner_r ** 2
            outside_mask = (dx_o ** 2 + dz_o ** 2) > outer_r ** 2
        else:
            dx_i = X - inner_c[0]; dy_i = Y - inner_c[1]
            dx_o = X - outer_c[0]; dy_o = Y - outer_c[1]
            inside_mask = (dx_i ** 2 + dy_i ** 2) < inner_r ** 2
            outside_mask = (dx_o ** 2 + dy_o ** 2) > outer_r ** 2
        Ex_m = np.where(inside_mask | outside_mask, np.nan, Ex)
        Ey_m = np.where(inside_mask | outside_mask, np.nan, Ey)

    elif mode == 'plates':
        plate_mask = (np.abs(Y - (-d / 2)) < (d / 20 + 1e-9)) | (np.abs(Y - (d / 2)) < (d / 20 + 1e-9))
        Ex_m = np.where(plate_mask, np.nan, Ex)
        Ey_m = np.where(plate_mask, np.nan, Ey)

    else:
        if plane == 'xz':
            m1 = (X - c0[0]) ** 2 + (Y - c0[2]) ** 2 < R1 ** 2
            m2 = (X - c1[0]) ** 2 + (Y - c1[2]) ** 2 < R2 ** 2
        else:
            m1 = (X - c0[0]) ** 2 + (Y - c0[1]) ** 2 < R1 ** 2
            m2 = (X - c1[0]) ** 2 + (Y - c1[1]) ** 2 < R2 ** 2
        mask = m1 | m2
        Ex_m = np.where(mask, np.nan, Ex)
        Ey_m = np.where(mask, np.nan, Ey)

    step = max(1, grid_size // 25)
    Xs, Ys = X[::step, ::step], Y[::step, ::step]
    el_field_xs, el_field_ys = Ex_m[::step, ::step], Ey_m[::step, ::step]
    el_field_xs_ma = np.ma.masked_invalid(el_field_xs)
    el_field_ys_ma = np.ma.masked_invalid(el_field_ys)

    try:
        sp_func = getattr(ax, 'streamplot', None)
        if sp_func is None:
            raise RuntimeError('streamplot not available on this axes')
        sp_func(Xs, Ys, el_field_xs_ma, el_field_ys_ma,
                color='white', linewidth=0.8, density=1.8,
                arrowsize=1.0, minlength=0.05)
    except Exception as e:
        logger.warning(f"Ошибка при отрисовке потоков: {e}")

    try:
        E_masked = np.where(np.isnan(Ex_m) | np.isnan(Ey_m), np.nan, np.sqrt(Ex ** 2 + Ey ** 2))
    except Exception:
        E_masked = np.where(np.isnan(E_magnitude), np.nan, E_magnitude)

    E_plot_vals = np.nan_to_num(E_masked, nan=np.nan)
    try:
        if np.all(np.isnan(E_plot_vals)):
            contour = ax.pcolormesh(X, Y, np.zeros_like(E_plot_vals), cmap='plasma', shading='auto')
        else:
            with np.errstate(invalid='ignore'):
                contour = ax.contourf(X, Y, E_plot_vals, levels=30, cmap='plasma', alpha=0.9)
    except Exception:
        contour = ax.pcolormesh(X, Y, np.nan_to_num(E_plot_vals, nan=0.0), cmap='plasma', shading='auto')

    if mode == 'separated':
        if plane == 'xz':
            p1 = (c0[0], c0[2]); p2 = (c1[0], c1[2])
        else:
            p1 = (c0[0], c0[1]); p2 = (c1[0], c1[1])

        cover1 = plt.Circle(p1, R1, facecolor='#e74c3c', edgecolor='none', zorder=1000, fill=True)
        cover2 = plt.Circle(p2, R2, facecolor='#3498db', edgecolor='none', zorder=1000, fill=True)
        ax.add_patch(cover1)
        ax.add_patch(cover2)
        ring1_top = plt.Circle(p1, R1, facecolor='none', edgecolor='#e74c3c', linewidth=2.5, zorder=1001, fill=False)
        ring2_top = plt.Circle(p2, R2, facecolor='none', edgecolor='#3498db', linewidth=2.5, zorder=1001, fill=False)
        ax.add_patch(ring1_top)
        ax.add_patch(ring2_top)

    if mode == 'concentric':
        elts = result.get('elements', [])
        if elts:
            c0 = np.mean([e.center for e in elts if e.sphere_id == 0], axis=0)
            c1 = np.mean([e.center for e in elts if e.sphere_id == 1], axis=0)
        else:
            c0 = np.array([0.0, 0.0, 0.0]); c1 = np.array([0.0, 0.0, 0.0])

        if R1 <= R2:
            inner_center, outer_center = c0, c1
            inner_r, outer_r = R1, R2
            inner_label = f'Внутр. сфера R={R1:.3f}м (+V/2)'
            outer_label = f'Внеш. сфера R={R2:.3f}м (−V/2)'
        else:
            inner_center, outer_center = c1, c0
            inner_r, outer_r = R2, R1
            inner_label = f'Внутр. сфера R={R2:.3f}м (+V/2)'
            outer_label = f'Внеш. сфера R={R1:.3f}м (−V/2)'
        if plane == 'xz':
            ic = (inner_center[0], inner_center[2]); oc = (outer_center[0], outer_center[2])
        else:
            ic = (inner_center[0], inner_center[1]); oc = (outer_center[0], outer_center[1])

        inner_ring = plt.Circle(ic, inner_r, facecolor='none', fill=False, edgecolor='#c0392b', linewidth=3.2, zorder=6, label=inner_label)
        outer_ring = plt.Circle(oc, outer_r, facecolor='none', fill=False, edgecolor='#2980b9', linewidth=3.2, zorder=6, label=outer_label)
        ax.add_patch(inner_ring)
        ax.add_patch(outer_ring)

        halo_outer = plt.Circle(oc, outer_r, facecolor='none', fill=False, edgecolor='#2980b9', linewidth=6.0, alpha=0.8, zorder=1000)
        ring_outer = plt.Circle(oc, outer_r, facecolor='none', fill=False, edgecolor='#2980b9', linewidth=4.0, zorder=1001)
        halo_inner = plt.Circle(ic, inner_r, facecolor='none', fill=False, edgecolor='#c0392b', linewidth=6.0, alpha=0.8, zorder=1000)
        ring_inner = plt.Circle(ic, inner_r, facecolor='none', fill=False, edgecolor='#c0392b', linewidth=4.0, zorder=1001)
        for p in (halo_outer, ring_outer, halo_inner, ring_inner):
            p.set_clip_on(True)
            ax.add_patch(p)
    elif mode == 'plates':
        x_min, x_max = X.min(), X.max()
        plate_thickness = max( (x_max - x_min) * 0.02, 0.001 )
        rect1 = plt.Rectangle((-R1, -d / 2 - plate_thickness / 2), 2 * R1, plate_thickness,
                              color='#e74c3c', zorder=4, alpha=0.9, label='Пластина 1 (+V/2)')
        rect2 = plt.Rectangle((-R2, d / 2 - plate_thickness / 2), 2 * R2, plate_thickness,
                              color='#3498db', zorder=4, alpha=0.9, label='Пластина 2 (−V/2)')
        ax.add_patch(rect1)
        ax.add_patch(rect2)
    else:
        ring1 = plt.Circle((0, 0), R1, facecolor='none', edgecolor='#e74c3c',
                           linewidth=2.5, zorder=5, label=f'Сфера 1  R={R1:.3f}м (+V/2)', fill=False)
        ring2 = plt.Circle((d,  0), R2, facecolor='none', edgecolor='#3498db',
                           linewidth=2.5, zorder=5, label=f'Сфера 2  R={R2:.3f}м (−V/2)', fill=False)
        ax.add_patch(ring1)
        ax.add_patch(ring2)

    try:
        _ = result.get('elements', [])
    except Exception as e:
        logger.warning(f"charge overlay warning: {e}")

    ax.set_xlabel('X (м)', fontsize=12)
    ax.set_ylabel('Y (м)', fontsize=12)
    if mode == 'plates':
        title = (f'Поле плоского конденсатора (сечение XZ)\n'
                 f'V={result["V"]:.1f} В,  d={d:.3f} м,  '
                 f'Q₁={result["Q1"]:.3e} Кл')
    elif mode == 'concentric':
        title = (f'Поле концентрических сфер (сечение XZ)\n'
                 f'V={result["V"]:.1f} В,  R₁={R1:.3f} м,  R₂={R2:.3f} м,  '
                 f'Q₁={result["Q1"]:.3e} Кл')
    else:
        title = (f'Силовые линии электрического поля (сечение XY)\n'
                 f'V={result["V"]:.1f} В,  d={d:.3f} м,  '
                 f'Q₁={result["Q1"]:.3e} Кл,  Q₂={result["Q2"]:.3e} Кл')

    ax.set_title(title, fontsize=13, pad=12, color='white')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    for spine in ax.spines.values():
        spine.set_edgecolor('white')
    ax.set_aspect('equal')
    leg = ax.legend(loc='upper right', fontsize=9, framealpha=0.5)
    for text in leg.get_texts():
        text.set_color('white')
    ax.grid(True, alpha=0.15, color='white')

    cbar = plt.colorbar(contour, ax=ax)
    cbar.set_label('|E| (В/м)', rotation=270, labelpad=20, fontsize=11, color='white')
    cbar.ax.yaxis.set_tick_params(color='white')
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color='white')

    fig.patch.set_facecolor('#0d0d1a')
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    img = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img


@router.get("/")
async def render_m21_page(request: Request):
    return templates.TemplateResponse("physics/M21.html", {"request": request})


@router.post("/calculate", response_model=ElectrostaticsResponse)
async def calculate_electrostatics(params: ElectrostaticsRequest):
    try:
        logger.info(f"Запрос: {params.model_dump()}")

        result = solve_electrostatics(
            R1=params.R1, R2=params.R2, d=params.d, V=params.V,
            n_divisions=params.n_divisions, mode=params.mode
        )

        field_viz = create_field_visualization(result)

        return ElectrostaticsResponse(
            success=True,
            mode=result['mode'],
            Q1=result['Q1'], Q2=result['Q2'],
            C_numerical=result['C_numerical'],
            C_analytical=result['C_isolated'],
            n_elements=result['n_elements'],
            field_img=field_viz
        )

    except ValueError as e:
        logger.error(f"Ошибка валидации: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка расчёта: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта: {str(e)}")


@router.get("/theory")
async def get_theoretical_values(R1: float, R2: float, d: Optional[float] = None):
    try:
        theory = calculate_capacitance_theoretical(R1, R2, d)
        return {"success": True, **theory}
    except Exception as e:
        logger.error(f"Ошибка теории: {e}")
        raise HTTPException(status_code=500, detail=str(e))
