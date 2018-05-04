#!/usr/bin/env python

import bin_to_geotiff
import sys, argparse
from os import system, path, listdir, remove, makedirs
import glob
from PIL import Image
from shutil import copyfile, rmtree
import multiprocessing
#from src import bin_to_geotiff_no_bounds

# Define that GPS bounds of interest -- we'll ignore any data that are outside of these bounds
# Order is: (SW_lat,SW_lng,NE_lat,NE_lng)
# full field
GPS_BOUNDS = (33.072616729424254, -111.97499111294746, 33.07404171941707, -111.9747644662857)

# small portion
#GPS_BOUNDS = (33.0726210139812, -111.97496797889471, 33.07264875823835, -111.97492665611207)

# designate the folder name for saving the tiles -- this will be a subdirectory under input_folder


def options():
    
    parser = argparse.ArgumentParser(description='Full Field Stitching Extractor in Roger',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument("-i", "--in_dir", help="input, stereo top bin files parent directory")
    parser.add_argument("-o", "--out_dir", help="output parent directory")
    parser.add_argument("-d", "--date", help="scan date")

    args = parser.parse_args()

    return args

def main():
    
    args = options()
    in_dir = path.join(args.in_dir, args.date)
    out_dir = path.join(args.out_dir, args.date)
    if not path.isdir(in_dir) or not path.isdir(args.out_dir):
        return
    
    subdirs = listdir(in_dir)
    
    TILE_FOLDER_NAME = 'tiles_' + args.date

    # Create a file to write the paths for all of the TIFFs. This will be used create the VRT.
    tif_file_list = path.join(out_dir,'tif_list.txt')
    
    # If there is a pre-existing tiles folder with this name, delete it (failing to do so can result in some weirdness when you load tiles later)
    if path.exists(out_dir):
        rmtree(out_dir)
    
    makedirs(out_dir)
    
    if path.exists(tif_file_list):
        try:
            remove(tif_file_list) # start from a fresh list of TIFFs for the day
        except OSError:
            pass

    # Convert binary files that are within GPS bounds to JPGs and GeoTIFFs
    print "Starting binary to image conversion..."
    for subdir in subdirs:
        in_path = path.join(in_dir, subdir)
        out_path = path.join(out_dir, subdir)
        try:
            bin_to_geotiff.main(in_path,out_path,tif_file_list, GPS_BOUNDS)
        except Exception as ex:
            fail("\tFailed to process folder %s: %s" % (in_path, str(ex)))
    print "Completed binary to image conversion..."
    print "Found " + str(file_len(tif_file_list)) + " folders within GPS bounds."
    
    # Create VRT from every GeoTIFF
    print "Starting VRT creation..."
    createVrt(out_dir,tif_file_list)
    print "Completed VRT creation..."

    # Generate tiles from VRT
    print "Starting map tile creation..."
    createMapTiles(out_dir, TILE_FOLDER_NAME)
    print "Completed map tile creation..."
    
    # Generate google map html template
    print "Starting google map html creation..."
    generate_googlemaps(out_dir, path.join(out_dir, TILE_FOLDER_NAME))
    print "Completed google map html creation..."
    
def generate_googlemaps(base_dir, tiles_dir):

        s = """
            <!DOCTYPE html>
                <html>
                  <head>
                    <title>Map Create By Left Sensor</title>
                    <meta name="viewport" content="initial-scale=1.0">
                    <meta charset="utf-8">
                    <style>
                      html, body {
                        height: 100%%;
                        margin: 0;
                        padding: 0;
                      }
                      #map {
                        height: 100%%;
                      }
                    </style>
                  </head>
                  <body>
                    <div id="map"></div>
                    <script>
                      function initMap() {
                          var MyCenter = new google.maps.LatLng(33.07547558,-111.97504675);
                  var map = new google.maps.Map(document.getElementById('map'), {
                    center: MyCenter,
                    zoom: 18,
                    streetViewControl: false,
                    mapTypeControlOptions: {
                      mapTypeIds: ['Terra']
                    }
                  });
                  
                
                
                  var terraMapType = new google.maps.ImageMapType({
                    getTileUrl: function(coord, zoom) {
                        var bound = Math.pow(2, zoom);
                        var y = bound-coord.y-1;
                       return '%s' +'/' + zoom + '/' + coord.x + '/' + y + '.jpg';
                    },
                    tileSize: new google.maps.Size(256, 256),
                    maxZoom: 28,
                    minZoom: 18,
                    radius: 1738000,
                    name: 'Terra'
                  });
                  
                  map.mapTypes.set('Terra', terraMapType);
                  map.setMapTypeId('Terra');
                }
                
                    </script>
                    <script src="https://maps.googleapis.com/maps/api/js?key=AIzaSyDJW9xwkAN3sfZE4FvGGLcgufJO9oInIHk&callback=initMap"async defer></script>
                  </body>
                </html>
            """ % tiles_dir
        
        f = open(path.join(base_dir, 'opengooglemaps.html'), 'w')
        f.write(s)
        f.close()

        return s


def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i+1

def bin_to_ims(base_dir,subdirs,tif_file_list):
    for s in subdirs:
        #Generate jpgs and geoTIFs from .bin
        try:
            bin_to_geotiff.main(s,s,tif_file_list, GPS_BOUNDS)
        except Exception as ex:
            fail("\tFailed to process folder %s: %s" % (s, str(ex)))

def createVrt(base_dir,tif_file_list):
    # Create virtual tif for the files in this folder
    # Build a virtual TIF that combines all of the tifs that we just created
    print "\tCreating virtual TIF..."
    try:
        vrtPath = path.join(base_dir,'virtualTif.vrt')
        cmd = 'gdalbuildvrt -srcnodata "-99 -99 -99" -overwrite -input_file_list ' + tif_file_list +' ' + vrtPath
        print(cmd)
        system(cmd)
    except Exception as ex:
        fail("\tFailed to create virtual tif: " + str(ex))

def createVrtPermanent(base_dir, tif_file_list, out_vrt='virtualTif.vrt'):
    # Create virtual tif for the files in this folder
    # Build a virtual TIF that combines all of the tifs that we just created
    print "\tCreating virtual TIF..."
    try:
        vrtPath = path.join(base_dir, out_vrt)
        cmd = 'gdalbuildvrt -srcnodata "-99 -99 -99" -overwrite -input_file_list ' + tif_file_list +' ' + vrtPath
        print(cmd)
        system(cmd)
    except Exception as ex:
        fail("\tFailed to create virtual tif: " + str(ex))

def createMapTiles(base_dir, folder_name):
    # Create map tiles from the virtual tif
    # For now, just creating w/ local coordinate system. In the future, can make these actually georeferenced.
    print "\tCreating map tiles..."
    try:
        vrtPath = path.join(base_dir,'virtualTif.vrt')
        NUM_THREADS = 8
        cmd = 'python gdal2tiles_parallel.py --processes=' + str(NUM_THREADS) + ' -l -n -e -f JPEG -z "18-28" -s EPSG:4326 ' + vrtPath + ' ' + path.join(base_dir,folder_name)
        system(cmd)
    except Exception as ex:
        fail("Failed to generate map tiles: " + str(ex))

def fail(reason):
    print >> sys.stderr, reason

if __name__ == '__main__':
    
    main()
