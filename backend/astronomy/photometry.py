from typing import List, Dict, Any, Tuple
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
from photutils.aperture import (
    CircularAperture,
    CircularAnnulus,
    ApertureStats,
    aperture_photometry,
)

# แถบการดูดกลืนแสงมาตรฐานในช่วงคลื่น SPHEREx (0.75 - 5.0 um)
STANDARD_ABSORPTION_MARKERS: List[Dict[str, Any]] = [
    {"molecule": "H2O Ice / Vapor", "range_um": (2.95, 3.15)},
    {"molecule": "CH4 (Methane)", "range_um": (3.20, 3.45)},
    {"molecule": "CO / CO2", "range_um": (4.20, 4.70)},
]


def measure_single_band_flux(
    img_2d: np.ndarray,
    wcs_2d: WCS,
    ra_deg: float,
    dec_deg: float,
    r_ap: float = 3.0,
    r_in: float = 6.0,
    r_out: float = 10.0,
) -> Tuple[float, float, Tuple[float, float]]:
    """
    วัดค่า Net Flux (uJy) และ Uncertainty ณ พิกัด (RA, Dec) บนภาพ 2 มิติ
    ใช้สำหรับเปรียบเทียบความสว่างระหว่าง Epoch 1 และ Epoch 2 (ทั้งวัตถุเคลื่อนที่และดาวแปรแสง)
    """
    coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
    x_pix, y_pix = wcs_2d.world_to_pixel(coord)
    pos = [(float(x_pix), float(y_pix))]

    aperture = CircularAperture(pos, r=r_ap)
    annulus = CircularAnnulus(pos, r_in=r_in, r_out=r_out)

    clean_img = np.nan_to_num(img_2d, nan=0.0)
    ann_stats = ApertureStats(clean_img, annulus)
    bkg_median = float(np.atleast_1d(ann_stats.median)[0])
    bkg_std = float(np.atleast_1d(ann_stats.std)[0])

    phot_tbl = aperture_photometry(clean_img, aperture)
    raw_flux = float(phot_tbl["aperture_sum"][0])

    net_flux = raw_flux - (bkg_median * aperture.area)
    flux_err = float(np.sqrt(abs(net_flux) + (aperture.area * (bkg_std ** 2))))

    return round(net_flux, 2), round(flux_err, 2), (float(x_pix), float(y_pix))


def extract_102band_spectrum(
    cube_fits_path: str,
    target_ra_deg: float,
    target_dec_deg: float,
    r_ap: float = 3.0,
    r_in: float = 6.0,
    r_out: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    สกัดกราฟสเปกตรัมอินฟราเรดใกล้ 102 แบนด์ (0.75 - 5.0 um) จากไฟล์ Spectral Cube
    คืนค่าตรงตาม Schema `SpectrumBandPoint`
    """
    with fits.open(cube_fits_path) as hdul:
        cube_data = np.nan_to_num(hdul[0].data.astype(np.float64), nan=0.0)
        wcs_2d = WCS(hdul[0].header, naxis=2)

        num_bands = cube_data.shape[0]
        if len(hdul) > 1 and "WAVELENGTH" in hdul[1].columns.names:
            wavelengths = hdul[1].data["WAVELENGTH"]
        else:
            wavelengths = np.linspace(0.75, 5.0, num_bands)

    coord = SkyCoord(ra=target_ra_deg * u.deg, dec=target_dec_deg * u.deg, frame="icrs")
    x_pix, y_pix = wcs_2d.world_to_pixel(coord)
    pos = [(float(x_pix), float(y_pix))]

    aperture = CircularAperture(pos, r=r_ap)
    annulus = CircularAnnulus(pos, r_in=r_in, r_out=r_out)
    ap_area = float(aperture.area)

    spectrum_points: List[Dict[str, Any]] = []

    for idx in range(num_bands):
        band_slice = cube_data[idx]

        ann_stats = ApertureStats(band_slice, annulus)
        bkg_median = float(np.atleast_1d(ann_stats.median)[0])
        bkg_std = float(np.atleast_1d(ann_stats.std)[0])

        phot_tbl = aperture_photometry(band_slice, aperture)
        raw_flux = float(phot_tbl["aperture_sum"][0])

        net_flux = max(0.05, raw_flux - (bkg_median * ap_area))
        flux_err = max(0.1, float(np.sqrt(abs(net_flux) + (ap_area * (bkg_std ** 2)))))

        spectrum_points.append({
            "band": int(idx + 1),
            "wavelength_um": round(float(wavelengths[idx]), 4),
            "flux_ujy": round(net_flux, 2),
            "flux_err": round(flux_err, 2),
        })

    return spectrum_points


def detect_molecular_absorption_bands(
    spectrum_102_bands: List[Dict[str, Any]],
    drop_threshold_ratio: float = 0.78,
) -> List[str]:
    """
    ตรวจสอบร่องการดูดกลืนแสง (Absorption Dips) เทียบกับ Continuum ข้างเคียงโดยอัตโนมัติ
    เพื่อระบุโมเลกุลสำคัญ เช่น H2O Ice (3.05 um), CH4 Methane (3.32 um) และ CO/CO2 (4.45 um)
    """
    wls = np.array([pt["wavelength_um"] for pt in spectrum_102_bands])
    fluxes = np.array([pt["flux_ujy"] for pt in spectrum_102_bands])

    detected: List[str] = []

    molecule_checks = [
        ("H2O Ice (3.05 um)", (2.95, 3.15), (2.70, 2.90)),
        ("CH4 Methane (3.32 um)", (3.20, 3.45), (3.55, 3.85)),
        ("CO / CO2 (4.45 um)", (4.20, 4.70), (3.85, 4.15)),
    ]

    for label, (in_min, in_max), (cont_min, cont_max) in molecule_checks:
        band_mask = (wls >= in_min) & (wls <= in_max)
        cont_mask = (wls >= cont_min) & (wls <= cont_max)

        if np.any(band_mask) and np.any(cont_mask):
            min_in_band = float(np.min(fluxes[band_mask]))
            mean_continuum = float(np.mean(fluxes[cont_mask]))
            if mean_continuum > 1e-3 and (min_in_band / mean_continuum) <= drop_threshold_ratio:
                detected.append(label)

    return detected
