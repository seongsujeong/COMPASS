#! python

'''
Script to extract amplitude of CSLC,
with thermal noise correction and / or radiometric normalization applied
'''
import argparse

import numpy as np
from osgeo import gdal, osr

from h5_helpers import (DATA_PATH, METADATA_PATH, get_cslc_amplitude,
                        get_dataset_geotransform,
                        get_radiometric_normalization_correction,
                        get_resampled_noise_correction)

# Constants for dataset location in HDF5 file
PATH_CSLC_LAYER_IN_HDF = DATA_PATH
PATH_LOCAL_INCIDENCE_ANGLE = f'{DATA_PATH}/local_incidence_angle'
PATH_NOISE_LUT = '{METADATA_PATH}/noise_information/thermal_noise_lut'


def save_amplitude(amplitude_arr, geotransform_cslc, epsg_cslc,
                   amplitude_filename):
    '''
    Save mosaicked array into GDAL Raster

    Parameters
    ----------
    amplitude_arr: np.ndarray
        Amplitude image as numpy array
    geotransform_cslc: tuple
        Geotransform parameter for mosaic
    epsg_cslc: int
        EPSG for mosaic as projection parameter
    amplitude_filename: str
        GEOTIFF file name of the output raster
    '''

    # Create the projection from the EPSG code
    srs_out = osr.SpatialReference()
    srs_out.ImportFromEPSG(epsg_cslc)
    projection_out = srs_out.ExportToWkt()

    length_mosaic, width_mosaic = amplitude_arr.shape
    driver = gdal.GetDriverByName('GTiff')
    ds_out = driver.Create(amplitude_filename,
                           width_mosaic, length_mosaic, 1, gdal.GDT_Float32,
                           options=['COMPRESS=LZW', 'BIGTIFF=YES'])

    ds_out.SetGeoTransform(geotransform_cslc)
    ds_out.SetProjection(projection_out)

    ds_out.GetRasterBand(1).WriteArray(amplitude_arr)

    ds_out = None


def get_parser():
    '''
    Get the parser for CLI
    '''
    parser = argparse.ArgumentParser(
        description=('Extracts CSLC amplitude with thermal noise and / or '
                     'radiometric correction applied'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c',
                        dest='cslc_path',
                        type=str,
                        default='',
                        help='cslc file')

    parser.add_argument('-s',
                        dest='cslc_static_path',
                        type=str,
                        default=[],
                        help='CSLC static layer file')

    parser.add_argument('-o',
                        dest='out_path',
                        type=str,
                        default=None,
                        help='path to the output file')

    parser.add_argument('-p',
                        dest='pol',
                        type=str,
                        default='VV',
                        help='Polarization')

    parser.add_argument('--noise_correction_off',
                        dest='apply_noise_correction',
                        default=True,
                        action='store_false',
                        help='Turn off the noise correction')

    parser.add_argument('--radiometric_normalization_off',
                        dest='apply_radiometric_normalization',
                        default=True,
                        action='store_false',
                        help='Turn off the radiometric normalization')

    return parser


def main():
    '''
    Entrypoint of the script
    '''
    parser = get_parser()
    args = parser.parse_args()

    if not args.apply_noise_correction \
            and not args.apply_radiometric_normalization:
        return

    cslc_amplitude_arr = get_cslc_amplitude(args.cslc_path, args.pol)

    cslc_dataset_path = f'{DATA_PATH}/{args.pol}'
    cslc_geotransform = get_dataset_geotransform(args.cslc_path,
                                                 cslc_dataset_path)

    # Subtract noise correction if needed
    if args.apply_noise_correction:
        # Get noise correction resampled to CSLC geotransform and geogrid
        # shape
        noise_correction_arr = get_resampled_noise_correction(
            args.cslc_static_path, cslc_amplitude_arr.shape, cslc_geotransform)

        # Covert amplitude to power, subtract noise, and revert to amplitude
        cslc_amplitude_arr = \
            cslc_amplitude_arr ** 2 - noise_correction_arr
        cslc_amplitude_arr[cslc_amplitude_arr < 0.0] = 0.0
        cslc_amplitude_arr = np.sqrt(cslc_amplitude_arr)

    # Multiply radiometric normalization correction if needed
    if args.apply_radiometric_normalization:
        radiometric_normalization_arr = \
            get_radiometric_normalization_correction(args.cslc_static_path)

        cslc_amplitude_arr *= radiometric_normalization_arr

    epsg_cslc = get_dataset_geotransform(args.cslc_path, cslc_dataset_path)

    save_amplitude(cslc_amplitude_arr, cslc_geotransform, epsg_cslc,
                   args.out_path)


if __name__=='__main__':
    main()
