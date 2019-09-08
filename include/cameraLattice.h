//
//  cameraLattice.h
//  cameraLattice
//
//  Created by Daniele Federico on 14/12/14.
//
//

#ifndef CAMERA_LATTICE_H
#define CAMERA_LATTICE_H

#include <tbb/tbb.h>

#include <maya/MTypeId.h>
#include <maya/MDataBlock.h>
#include <maya/MMatrix.h>
#include <maya/MPxDeformerNode.h>
#include <maya/MItGeometry.h>

#include <maya/MVectorArray.h>
#include <maya/MPointArray.h>

#include <vector>

struct Influencer
{
    MMatrix invMat;
    MVector pos;
    double falloff;
    double maxAxisLength;
};

class CameraLatticeData
{
public:
    
	struct ThreadData
	{
        MMatrix *projectionMatrix;
        MMatrix *invProjectionMatrix;
        MMatrix *toWorldMatrix;
		MPointArray *points;
		MPointArray *deformedPoints;

        MPointArray *planePoints;
        
        double filmHAperture, filmVAperture;
        int sD, tD;
        int maxRecursion, behaviour;
        double gateOffsetValue;
        
        std::vector<Influencer> *influencers;
        
        double envelopeValue;
        
        bool isOrtho;
        
	};
    
    ~CameraLatticeData(){};
    
	CameraLatticeData(MMatrix *projectionMatrix,
                      MMatrix *invProjectionMatrix,
                      MMatrix *toWorldMatrix,
                      MPointArray *points,
                      MPointArray *deformedPoints,
                      MPointArray* planePoints,
                      double filmHAperture, double filmVAperture,
                      int sD, int tD, bool isOrtho, int maxRecursion, int behaviour,
                      std::vector<Influencer> *influencers, double gateOffsetValue, double envelopeValue)
	{
		m_data.projectionMatrix = projectionMatrix;
		m_data.invProjectionMatrix = invProjectionMatrix;
		m_data.points = points;
		m_data.deformedPoints = deformedPoints;
        m_data.planePoints = planePoints;
        m_data.filmHAperture = filmHAperture;
        m_data.filmVAperture = filmVAperture;
        m_data.sD = sD;
        m_data.tD = tD;
        m_data.isOrtho = isOrtho;
        m_data.maxRecursion = maxRecursion;
        m_data.behaviour = behaviour;
        m_data.influencers = influencers;
        m_data.toWorldMatrix = toWorldMatrix;
        m_data.gateOffsetValue = gateOffsetValue;
        m_data.envelopeValue = envelopeValue;
	}
    
	void operator()( const tbb::blocked_range<size_t>& r ) const;
    
    private:
    
        struct ThreadData m_data;
};

class CameraLattice : public MPxDeformerNode
{
public:
    CameraLattice();
	virtual				~CameraLattice();
    
	static  void*		creator();
	static  MStatus		initialize();
    
	// deformation function
	//
    virtual MStatus      		deform(MDataBlock& 		block,
									   MItGeometry& 	iter,
									   const MMatrix& 	mat,
									   unsigned int		multiIndex);
    
    virtual MStatus connectionMade (const MPlug &plug, const MPlug &otherPlug, bool asSrc);
    virtual MStatus connectionBroken (const MPlug &plug, const MPlug &otherPlug, bool asSrc);
    
    
public:
	// local node attributes
    
	static  MObject 	inputLattice;
	static  MObject		interpolation;
    static  MObject     deformerMessage;
    static  MObject     latticeToDeformerMessage;
    static  MObject     sSubidivision;
    static  MObject     tSubidivision;
    static  MObject     objectMatrix;
    static  MObject     cameraMatrix;
    static  MObject     inOrtho;
    static  MObject     inOrthographicWidth;
    static  MObject     inVerticalFilmAperture;
    static  MObject     inHorizontalFilmAperture;
    static  MObject     inFocalLength;
    static  MObject     maxBezierRecursion;
	static  MObject     influenceFalloff;
    static  MObject     influenceMatrix;
    static  MObject     gateOffset;
    
	static  MTypeId		id;

private:
    bool refreshLogicalIndex;
    MIntArray cachedLogicalIndex;

};

#endif
