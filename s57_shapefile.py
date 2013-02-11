#!/usr/bin/python
################################################################################
#
# s57_shapefile.py
#
# Copyright 2013 Crown copyright (c)
# Land Information New Zealand and the New Zealand Government.
# All rights reserved
#
# This program is released under the terms of the new BSD license. See the 
# LICENSE file for more information.
#
################################################################################
# Simple script to read a collection of s57 datasources, merge common feature 
# types and output to shapefile. Designed to produce input files to the LINZ
# Data Service (http://data.linz.govt.nz)
#
# Read here for more information about the OGR S57 driver:
# http://www.gdal.org/ogr/drv_s57.html
# OGR_S57_OPTIONS to look at are ADD_SOUNDG_DEPTH, LNAM_REFS, SPLIT_MULTIPOINT
# and RETURN_LINKAGES
################################################################################

import os
import sys
import glob
import argparse

__author__ = 'Jeremy Palmer'
__date__ = 'February 2013'
__copyright__ = '2013 Crown copyright (c)'
__version__ = '1.0.0'

try:
    from osgeo import ogr, osr, gdal
except:
    try:
        import ogr, osr, gdal
    except:
        print 'cannot find python OGR and GDAL modules'
        sys.exit( 1 )

feature_classes = {}
excluded_fields = [
    'RCID', 'PRIM', 'GRUP', 'OBJL', 'RVER', 'AGEN',
    'FIDN', 'FIDS', 'LNAM', 'LNAM_REFS', 'FFPT_RIND',
    'RECIND', 'RECDAT', 'SCAMAX'
]

# output CS in WGS84
output_srs = osr.SpatialReference()
output_srs.ImportFromEPSG( 4326 )

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

def wkbFlatten(x):
    return x & (~ogr.wkb25DBit)

def get_geom_types( layer ):
    types_dict = {}
    layer.ResetReading()
    f = layer.GetNextFeature()
    while f is not None:
        geom = f.GetGeometryRef()
        if geom is not None:
            geom_type = geom.GetGeometryType()
            types_dict[geom_type] = 1
        f = layer.GetNextFeature()
    return set(types_dict.keys())

def get_generic_types( wkbtypes ):
    generic_types_dict = {}
    for type in wkbtypes:
        generic_types_dict[get_generic_type(type)] = 1
    return generic_types_dict.keys()

def get_generic_type( wkbtype ):
    type = ""
    flat_type = wkbFlatten( wkbtype )
    if flat_type == ogr.wkbPolygon or flat_type == ogr.wkbMultiPolygon:
        type = 'Polygon'
    elif flat_type == ogr.wkbLineString or flat_type == ogr.wkbMultiLineString:
        type = 'Arc'
    elif flat_type == ogr.wkbPoint or flat_type == ogr.wkbMultiPoint:
        type = 'Point'
    else:
        print("ERROR: Geometry type not supported." )
        exit( 1 )
    return type

def read_datasets( files ):
    datasets = []
    for f in files:
        ds = ogr.Open( f )
        if ds is None:
            print( 's57 dataset is invalid %s.' % f )
            sys.exit( 1 )
        for i in range( 0, ds.GetLayerCount() ):
            lyr = ds.GetLayer( i )
            name = lyr.GetName()
            layer_geom_types = get_geom_types(lyr)
            if name in feature_classes and feature_classes[name]:
                feature_classes[name] = feature_classes[name].union(layer_geom_types)
            else:
                feature_classes[name] = layer_geom_types
        datasets.append( ds )
    return datasets

def create_fields(src_layer, dst_layer):
    lyr_defn = src_layer.GetLayerDefn()
    for i in range( lyr_defn.GetFieldCount() ):
        field = lyr_defn.GetFieldDefn( i )
        field_name = field.GetNameRef()
        if field_name in excluded_fields:
           continue
        type = field.GetType()
        if type == ogr.OFTStringList or \
            type == ogr.OFTIntegerList or \
            type == ogr.OFTRealList or \
            type == ogr.OFTBinary:
            type = ogr.OFTString
        new = ogr.FieldDefn( field_name, type )
        new.SetWidth( field.GetWidth() )
        new.SetPrecision( field.GetPrecision() )
        dst_layer.CreateField( new )
    return

def merge_datasets( input_datasources, dst_path, prefix ):
        
    for feature_class in feature_classes.keys():
        geom_types = feature_classes[feature_class]
        generic_types = get_generic_types( geom_types )
        for gen_type in generic_types:
            filename = feature_class + '_' + gen_type + '.shp'
            if prefix:
                filename = prefix + filename
            shapefile = os.path.join( dst_path, filename )
            if os.path.exists( shapefile ):
                shape_drv.DeleteDataSource( shapefile )
            
            shape_ds = shape_drv.CreateDataSource( shapefile )
            dest_shape_lyr = shape_ds.CreateLayer( feature_class, output_srs )
            output_schema_created = False
            
            for ds in input_datasources:
                lyr = ds.GetLayerByName( feature_class )
                if lyr is None:
                    #print( 'Warning: Datasource %s does not contain feature class %s'
                    #    % ( ds.GetName(), feature_class ) )
                    continue
                if not output_schema_created:
                    create_fields( lyr, dest_shape_lyr )
                    output_schema_created = True
                copy_data( ds, lyr, dest_shape_lyr, gen_type )
            shape_ds.Destroy()
    
    for ds in input_datasources:
        ds.Destroy()

def copy_data( ds, src_layer, dst_layer, type ):
    src_layer.ResetReading()
    while True:
        src_feature = src_layer.GetNextFeature()
        if src_feature is None:
            break
        geom = src_feature.GetGeometryRef()
        shift_geom( geom )
        if geom is not None:
            geom_type = geom.GetGeometryType()
            if type != get_generic_type( geom_type ):
                src_feature.Destroy()
                continue
        dst_feature = ogr.Feature( dst_layer.GetLayerDefn() )
        dst_feature.SetFrom( src_feature )
        if dst_layer.CreateFeature( dst_feature ) != 0:
            print( 'Could not write feature ID %s from feature class %s in %s' %
                ( src_feature.GetFID(), src_layer.GetName(), ds.GetName() ) )
        src_feature.Destroy()
        dst_feature.Destroy()
    return True

def main():
    input_files = []
    input_datasources = []
    
    parser = argparse.ArgumentParser(
        description = 'Script to read a collection of s57 datasources, merge common '
            'feature types and output to shapefile'
    )
    parser.add_argument('src_path', help='Source directory of S57 Files')
    parser.add_argument('dst_path', help='Output directory for created shapefiles')
    parser.add_argument("-p", "--prefix", help='Prefix to shapefile output name')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.src_path):
        print( 'Unable to open source directory %s ' % args.src_path )
        sys.exit( 1 )
    
    if not os.path.isdir( args.dst_path ):
        os.makedirs( args.dst_path )
    
    input_files = glob.glob( os.path.join( args.src_path, '*.000' ) )
    
    if len(input_files) < 1:
        print( 'No s57 files were found in %s ' % args.src_path )
        sys.exit( 1 )
    
    gdal.SetConfigOption(
        'OGR_S57_OPTIONS',
        'LNAM_REFS=ON,ADD_SOUNDG_DEPTH=ON,SPLIT_MULTIPOINT=ON'
    )
    input_datasources = read_datasets( input_files )
    
    merge_datasets( input_datasources, args.dst_path, args.prefix )

if __name__ == "__main__":
    main()

