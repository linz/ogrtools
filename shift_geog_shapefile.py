#!/usr/bin/python
################################################################################
#
# shift_geog_shapefile.py
#
# Copyright 2013 Crown copyright (c)
# Land Information New Zealand and the New Zealand Government.
# All rights reserved
#
# This program is released under the terms of the new BSD license. See the 
# LICENSE file for more information.
#
################################################################################
# Script to translate shapefile data to 0-360 longitude space. Source data
# must be in terms of a geographic coordinate system.
################################################################################

import os
import sys
import argparse

try:
    from osgeo import ogr, osr, gdal
except:
    try:
        import ogr, osr, gdal
    except:
        print 'cannot find python OGR and GDAL modules'
        sys.exit( 1 )

shape_drv = ogr.GetDriverByName( 'ESRI Shapefile' )
if shape_drv is None:
    print( 'Could not load ESRI Shapefile driver' )
    sys.exit( 1 )
    

def shift_geom ( geom ):
    if geom is None:
        return
    count = geom.GetGeometryCount()
    if count > 0:
        for i in range( count ):
            shift_geom( geom.GetGeometryRef( i ) )
    else:
        for i in range( geom.GetPointCount() ):
            x, y, z = geom.GetPoint( i )
            if x < 0:
                x = x + 360
            elif x > 360:
                x = x - 360
            geom.SetPoint( i, x, y, z )
    return


def shift_geog_file( src_shp_file, dst_shp_file, encoding ):
    src_shape_ds = ogr.Open(src_shp_file)
    if src_shape_ds is None:
        print( "Can't open shapefile for reading %s" % src_shp_file )
        exit( 1 )
    src_layer = src_shape_ds.GetLayer()
    spatial_ref_sys = src_layer.GetSpatialRef()
    if not spatial_ref_sys.IsGeographic():
        print( 'Source shapefile does not have a geographic coordinate system' )
    
    options = []
    if encoding is not None:
        options = ["ENCODING=" + encoding]
    if os.path.exists( dst_shp_file ):
        shape_drv.DeleteDataSource( dst_shp_file )
    dst_shape_ds = shape_drv.CreateDataSource( dst_shp_file )
    if dst_shape_ds is None:
        print( "Can't open shapefile for writing %s" % dst_shape_ds )
        exit( 1 )
    dst_layer = dst_shape_ds.CreateLayer( "", srs = spatial_ref_sys, geom_type = src_layer.GetGeomType(), options = options )
    
    
    lyr_defn = src_layer.GetLayerDefn()
    for i in range( lyr_defn.GetFieldCount() ):
        field = lyr_defn.GetFieldDefn( i )
        new = ogr.FieldDefn( field.GetNameRef(), field.GetType() )
        new.SetWidth( field.GetWidth() )
        new.SetPrecision( field.GetPrecision() )
        dst_layer.CreateField( new )
    
    src_layer.ResetReading()
    while True:
        src_feature = src_layer.GetNextFeature()
        if src_feature is None:
            break
        dst_feature = ogr.Feature( lyr_defn )
        dst_feature.SetFrom( src_feature )
        geom = dst_feature.GetGeometryRef()
        shift_geom( geom )
        
        if dst_layer.CreateFeature( dst_feature ) != 0:
            print( 'Could not write feature ID %s from feature class %s' % ( src_feature.GetFID(), src_layer.GetName() ) )
        src_feature.Destroy()
        dst_feature.Destroy()
    
    src_shape_ds.Destroy()
    dst_shape_ds.Destroy()

def main():

    parser = argparse.ArgumentParser(
        description = 'Script to translate shapefile data to 0-360 longitude space. '
            'Source data must be in terms of a geographic coordinate system'
    )
    parser.add_argument('src_shp_file', help='input shapefile')
    parser.add_argument('dst_shp_file', help='output shifted shapefile')
    parser.add_argument("-e", "--encoding", help='set the encoding value for shapefile file')
    args = parser.parse_args()
    
    src_shp_file = args.src_shp_file
    dst_shp_file = args.dst_shp_file
    encoding     = args.encoding
    
    if encoding is not None and encoding != '':
        gdal.SetConfigOption('SHAPE_ENCODING', encoding)
    
    shift_geog_file( src_shp_file, dst_shp_file, encoding )

if __name__ == "__main__":
    main()

