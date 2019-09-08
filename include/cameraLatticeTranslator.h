/*
 *  CameraLatticeTranslator.h
 *  CameraLatticeTranslator
 *
 *
 */

#ifndef CAMERA_LATTICE_TRANSLATOR_H
#define CAMERA_LATTICE_TRANSLATOR_H

#include <maya/MTypeId.h>
#include <maya/MPxNode.h>
#include <maya/MDataBlock.h>
#include <maya/MDataHandle.h>
#include <maya/MFnPluginData.h>
#include <maya/MFnNumericAttribute.h>
#include <math.h>
#include <maya/MGlobal.h> 


class CameraLatticeTranslator : public MPxNode
{
	public:
		static void *creator();
		static MStatus initialize();
		
		virtual MStatus compute( const MPlug& plug, MDataBlock& data );
		
		static MTypeId id;
		
		
	private:
		static MObject inNearClipPlane;
		static MObject inFocalLength;
		static MObject inHorizontalFilmAperture;
		static MObject inVerticalFilmAperture;
        static MObject inOrtho;
        static MObject inOrthographicWidth;
		static MObject outScaleX;
		static MObject outScaleY;
		static MObject outTranslateZ;
		
};

#endif
