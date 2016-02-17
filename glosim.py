#!/usr/bin/env python
# Computes the matrix of similarities between structures in a xyz file
# by first getting SOAP descriptors for all environments, finding the best
# match between environments using the Hungarian algorithm, and finally
# summing up the environment distances.
# Supports periodic systems, matching between structures with different
# atom number and kinds, and sports the infrastructure for introducing an
# alchemical similarity kernel to match different atomic species

import quippy
import sys, time,ast
from multiprocessing import Process, Value, Array
import argparse
from random import randint
from libmatch.environments import alchemy, environ
from libmatch.structures import structk, structure
import os
import numpy as np
from copy import copy 
import cPickle as pickle
class structurelist(list):

    def __init__(self, lowmem=False, basedir="tmpstructures"):
        self.basedir=basedir
        if lowmem:
          if not os.path.exists(basedir):os.makedirs(basedir)
         # create the folder if it is not there
        self.lowmem=lowmem
#        self.storage=[]
        self.count=0
        
    def append(self, element):
#        if self.lowmem:
            #piclke
            # self.storage.append("filename where the new element is stored")
            ind=self.count
            f=self.basedir+'/sl_'+str(ind)+'.dat'
            file=open(f,"w")
            pickle.dump(element, file)
            file.close()
            self.count+=1
#        else:
#            super(structurelist,self).append(element)

    def __getitem__(self, index):

#        if self.lowmem:
            f=self.basedir+'/sl_'+str(index)+'.dat'
            file=open(f,"r")
            l=pickle.load(file)
            return  l
            file.close()
            #pass
#        else:
#            val=list.__getitem__(self, index)
#            return  val

def main(filename, nd, ld, coff, gs, mu, centerweight, periodic, kmode, permanenteps, reggamma, nocenter, noatom, nprocs, verbose=False, envij=None, usekit=False, kit="auto", alchemyrules="none",prefix="",nlandmark=0, printsim=False,ref_xyz="",partialsim=False,lowmem=False):
    print >>sys.stderr, "    ___  __    _____  ___  ____  __  __ ";
    print >>sys.stderr, "   / __)(  )  (  _  )/ __)(_  _)(  \/  )";
    print >>sys.stderr, "  ( (_-. )(__  )(_)( \__ \ _)(_  )    ( ";
    print >>sys.stderr, "   \___/(____)(_____)(___/(____)(_/\/\_)";
    print >>sys.stderr, "                                        ";
    print >>sys.stderr, "                                         ";
    filename = filename[0]
    # sets a few defaults
    if lowmem :
       print >> sys.stderr,"!!!!!!!!!!!!!!!!!!! LOW MEMORY OPTION ACTIVATED !!!!!!!!!!!!!!!!!!!!!!!!"
       print >> sys.stderr,"Descriptors will be written in tmpstructures dir instead of storing in memory"
       print >> sys.stderr,"       Things are about to get SLOOOOOOOOOOOOOOOOOW !!! "
       print >> sys.stderr," ========================================================================="
       print >> sys.stderr,"   "
    if prefix=="": prefix=filename
    if prefix.endswith('.xyz'): prefix=prefix[:-4]

    # reads input file using quippy
    print >> sys.stderr, "Reading input file", filename
    al = quippy.AtomsList(filename);
    print >> sys.stderr, len(al.n) , " Configurations Read"
    if (ref_xyz !=""):
        print >> sys.stderr, "================================REFERENCE XYZ FILE GIVEN=====================================\n",
        print >> sys.stderr, "Only Rectangular Matrix Containing Distances Between Two Sets of Input Files Will be Computed.\n",
        print >> sys.stderr, "Reading Referance xyz file: ", ref_xyz
        alref = quippy.AtomsList(ref_xyz);
        print >> sys.stderr, len(alref.n) , " Configurations Read"


    print >> sys.stderr, "Computing SOAPs"
    # sets alchemical matrix
    if (alchemyrules=="none"):
       alchem = alchemy(mu=mu)
    else:
       r=alchemyrules.replace('"', '').strip()
       r=alchemyrules.replace("'", '').strip()
       r=ast.literal_eval(r)
       print >> sys.stderr, "Using Alchemy rules: ", r,"\n"
       alchem = alchemy(mu=mu,rules=r)
      
    if lowmem:
       sl = structurelist(lowmem=lowmem)
    else:
       sl=[]
    iframe = 0      
    if verbose:
        qlog=quippy.AtomsWriter("log.xyz")
        slog=open("log.soap", "w")
      
    # determines reference kit    
    if usekit:
        if kit == "auto": 
            kit = {} 
            iframe=0
            for at in al:
                if envij == None or iframe in envij: 
                    sp = {} 
                    for z in at.z:     
                        if z in noatom or z in nocenter: continue  
                        if z in sp: sp[z]+=1
                        else: sp[z] = 1
                    for s in sp:
                        if not s in kit:
                            kit[s]=sp[s]
                        else:
                            kit[s]=max(kit[s], sp[s])
                iframe+=1
        iframe=0
        print >> sys.stderr, "Using kit: ", kit
    else: kit=None
    nf = len(al.n)  
    nf_ref=nf 
    iframe=0 
    nrm = np.zeros(nf,float)
    for at in al:
        if envij == None or iframe in envij:
            sys.stderr.write("Frame %d                              \r" %(iframe) )
            if verbose: qlog.write(at)

            # parses one of the structures, topping up atoms with isolated species if requested
            si = structure(alchem)
            si.parse(at, coff, nd, ld, gs, centerweight, nocenter, noatom, kit = kit)
            sl.append(si)
            if verbose:
                slog.write("# Frame %d \n" % (iframe))
                fii = open(prefix+".environ-"+str(iframe)+"-"+str(iframe)+".dat", "w")
                for sp, el in si.env.iteritems():
                    ik=0
                    for ii in el:
                        slog.write("# Species %d Environment %d \n" % (sp, ik))
                        ik+=1
                        for p, s in ii.soaps.iteritems():
                            slog.write("%d %d   " % p)
                            for si in s:
                                slog.write("%8.4e " %(si))                        
                            slog.write("\n")
            else:
               fii = None
             
            sii = structk(si, si, alchem, periodic, mode=kmode, fout=fii, peps=permanenteps, gamma=reggamma)        
            nrm[iframe]=sii        
        iframe +=1; 
      
    print >> sys.stderr, "Computing kernel matrix"
    # must fix the normalization of the similarity matrix!
#    sys.stderr.write("Computing kernel normalization           \n")
#    nrm = np.zeros(nf,float)
#    for iframe in range (0, nf):           
#        if verbose:
#            fii = open(prefix+".environ-"+str(iframe)+"-"+str(iframe)+".dat", "w")
#        else:
#            fii = None
#        sii = structk(sl[iframe], sl[iframe], alchem, periodic, mode=kmode, fout=fii, peps=permanenteps, gamma=reggamma)        
#        nrm[iframe]=sii        

    
    if (ref_xyz !=""): # If ref landmarks are given and rectangular matrix is the only desired output             
        print >> sys.stderr, "Computing SOAPs"
        # sets alchemical matrix
        alchem = alchemy(mu=mu)
        if (lowmem):
          sl_ref = structurelist(lowmem=lowmem)
        else:
          sl_ref=[]
        iframe = 0
        if verbose:
            qlogref=quippy.AtomsWriter("log_ref.xyz")
            slogref=open("log_ref.soap", "w")

        # determines reference kit    
        if usekit:
            if kit == "auto":
                kit = {}
                iframe=0
                for at in alref:
                    if envij == None or iframe in envij:
                        sp = {}
                        for z in at.z:
                            if z in noatom or z in nocenter: continue
                            if z in sp: sp[z]+=1
                            else: sp[z] = 1
                        for s in sp:
                            if not s in kit:
                                kit[s]=sp[s]
                            else:
                                kit[s]=max(kit[s], sp[s])
                    iframe+=1
            iframe=0
            print >> sys.stderr, "Using kit: ", kit
        else: kit=None
        nf_ref = len(alref.n)
        nrm_ref = np.zeros(nf_ref,float)
        iframe=0
        for at in alref:
            if envij == None or iframe in envij:
                sys.stderr.write("Frame %d                              \r" %(iframe) )
                if verbose: qlogref.write(at)

                # parses one of the structures, topping up atoms with isolated species if requested
                si = structure(alchem)
                si.parse(at, coff, nd, ld, gs, centerweight, nocenter, noatom, kit = kit)
                sl_ref.append(si)
                sii = structk(si, si, alchem, periodic, mode=kmode, fout=None, peps = permanenteps, gamma=reggamma)        
                nrm_ref[iframe]=sii        
                if verbose:
                    slog.write("# Frame %d \n" % (iframe))
                    for sp, el in si.env.iteritems():
                        ik=0
                        for ii in el:
                            slogref.write("# Species %d Environment %d \n" % (sp, ik))
                            ik+=1
                            for p, s in ii.soaps.iteritems():
                                slogref.write("%d %d   " % p)
                                for si in s:
                                    slogref.write("%8.4e " %(si))
                                slogref.write("\n")

            iframe +=1;

        print >> sys.stderr, "Computing kernel matrix"
        # must fix the normalization of the similarity matrix!
     #   sys.stderr.write("Computing kernel normalization           \n")
#        for iframe in range (0, nf_ref):           

        sim = np.zeros((nf,nf_ref))
        sys.stderr.write("Computing Similarity Matrix           \n")
        
        if (nprocs<=1):
         for iframe in range(nf):
           sys.stderr.write("Matrix row %d                           \r" % (iframe))
           for jframe in range(nf_ref):
             sij = structk(sl[iframe], sl_ref[jframe], alchem, periodic, mode=kmode, fout=None, peps = permanenteps, gamma=reggamma)
             sim[iframe][jframe]=sij/np.sqrt(nrm[iframe]*nrm_ref[jframe])
        else:    
        # multiple processors
            def dorow(irow, nf_ref, psim): 
                for jframe in range(0,nf_ref):
                    sij = structk(sl[iframe], sl_ref[jframe], alchem, periodic, mode=kmode,fout=None, peps = permanenteps, gamma=reggamma)          
                    psim[irow*nf_ref+jframe]=sij/np.sqrt(nrm[irow]*nrm_ref[jframe])  
               
            proclist = []   
            psim = Array('d', nf*nf_ref, lock=False)      
            for iframe in range (0, nf):
                while(len(proclist)>=nprocs):
                    for ip in proclist:
                        if not ip.is_alive(): proclist.remove(ip)            
                        time.sleep(0.01)
                sp = Process(target=dorow, name="doframe proc", kwargs={"irow":iframe, "nf_ref":nf_ref, "psim": psim})  
                proclist.append(sp)
                sp.start()
                sys.stderr.write("Matrix row %d, %d active processes     \r" % (iframe, len(proclist)))
            
            # waits for all threads to finish
            for ip in proclist:
                while ip.is_alive(): ip.join(0.1)  
         
            # copies from the shared memory array to Sim.
            for iframe in range (0, nf):      
                for jframe in range(0,nf_ref):
                    sim[iframe,jframe]=psim[iframe*nf_ref+jframe]   
        #===================================================================            
                    
        fkernel = open(prefix+"_rect.k", "w")  
        fkernel.write("# OOS Kernel matrix for %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s " % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)) )
        if (usekit):fkernel.write( " Using reference kit: %s " % (str(kit)) )
        if (alchemyrules!="none"):fkernel.write( " Using alchemy rules: %s " % (alchemyrules) )
        if (kmode=="regmatch"): fkernel.write( " Regularized parameter: %f " % (reggamma) )
        fkernel.write("\n")
        for iframe in range(0,nf):
            for x in sim[iframe][0:nf_ref]:
                fkernel.write("%16.8e " % (x))
            fkernel.write("\n")   
            
        if printsim:
            fsim = open(prefix+"_rect.sim", "w")  
            fsim.write("# OOS Distance matrix for %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s " % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)) )
            if (usekit):fsim.write( " Using reference kit: %s " % (str(kit)) )
            if (alchemyrules!="none"):fsim.write( " Using alchemy rules: %s " % (alchemyrules) )
            if (kmode=="regmatch"): fsim.write( " Regularized parameter: %f " % (reggamma) )
            fsim.write("\n")
            for iframe in range(0,nf):
                for x in sim[iframe][0:nf_ref]:
                    fsim.write("%16.8e " % (np.sqrt(max(2-2*x,0))))
                fsim.write("\n")   

#=============================================================================
            
   
    elif (nlandmark>0): # we have just one input but we compute landmarks
        print >> sys.stderr, "##### FARTHEST POINT SAMPLING ######"
        print >> sys.stderr, "Selecting",nlandmark,"Frames from",nf, "Frames"
        print >> sys.stderr, "####################################"
        landlist=open(prefix+".landmarks","w")
        landxyz=quippy.AtomsWriter(prefix+".landmarks.xyz")   
        if (partialsim): 
          pfkernel=open(prefix+".k.partial","w")
          pfkernel.write("# Kernel matrix for OOS from %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s" % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)) )
          if (usekit):pfkernel.write( " Using reference kit: %s " % (str(kit)) )
          if (alchemyrules!="none"):pfkernel.write( " Using alchemy rules: %s " % (alchemyrules) )
          if (kmode=="regmatch"): pfkernel.write( " Regularized parameter: %f " % (reggamma) )
          pfkernel.write("\n")
 
        m = nlandmark
        sim = np.zeros((m,m))
        sim_rect=np.zeros((m,nf))
        dist_list=[]
        landmarks=[]         
        iframe=0       
#        iframe=randint(0,nf-1)  # picks a random frame
        iland=0
        landmarks.append(iframe)
        for jframe in range(nf):            
            sij = structk(sl[iframe], sl[jframe], alchem, periodic, mode=kmode, fout=None,peps = permanenteps, gamma=reggamma)
            sim_rect[iland][jframe]=sij/np.sqrt(nrm[iframe]*nrm[jframe])
            dist_list.append(np.sqrt(max(0,2-2*sij))) # use kernel metric
        #for x in sim_rect[iland][:]:
        #    fsim.write("%8.4e " %(x))
        #fsim.write("\n")
        landlist.write("# Landmark list\n")
        landlist.write("%d\n" % (landmarks[0]))
        landxyz.write(al[landmarks[0]])
        if(partialsim):
            for x in sim_rect[iland,:]:
                pfkernel.write("%20.12e " % (x))
            pfkernel.write("\n")
        for iland in range(1,m):
            maxd=0.0
            for jframe in range(nf):
                if(dist_list[jframe]>maxd):
                    maxd=dist_list[jframe]
                    maxj=jframe
            landmarks.append(maxj)
            landxyz.write(al[maxj])
            landlist.write("%d\n" % (maxj))
            
            sys.stderr.write("Landmark %5d    maxd %f                          \r" % (iland, maxd))
            iframe=maxj
            if (nprocs<=1):
             for jframe in range(nf):                
                sij = structk(sl[iframe], sl[jframe], alchem, periodic, mode=kmode, fout=None, peps = permanenteps, gamma=reggamma)
                sim_rect[iland][jframe]=sij/np.sqrt(nrm[iframe]*nrm[jframe])
                dij = np.sqrt(max(0,2-2*sij))
                if(dij<dist_list[jframe]): dist_list[jframe]=dij
            else:
		      # multiple processors
              def docol(iproc,pdist,psim,iframe,jframe1,jframe2):
                  for jframe in range(jframe1,jframe2):                                
                     sij = structk(sl[iframe], sl[jframe], alchem, periodic, mode=kmode, fout=None, peps = permanenteps, gamma=reggamma)
                     psim[jframe]=sij/np.sqrt(nrm[iframe]*nrm[jframe])
                     dij= np.sqrt(max(0,2-2*sij))
                     if(dij<dist_list[jframe]): pdist[iproc*nf+jframe]=dij
               #   print iframe,jframe
               
              proclist = []   
              pdist = Array('d', nf*nprocs, lock=False)
              psim = Array('d', nf, lock=False)
              for iproc in range(nprocs):
                 for jframe in range(nf):pdist[iproc*nf+jframe]=dist_list[jframe]
              jframe_split_list=[]
              fpp=int(nf/nprocs)
              for i in range(nprocs):
                jframe_split_list.append(i*fpp)
              jframe_split_list.append(nf)
           #   if(iland==1):print "jframe splitlist",jframe_split_list,'\n'
              for iproc in range(1,nprocs+1): 
                 while(len(proclist)>=nprocs):
                    #print "proclist",proclist
                    for ip in proclist:
                        if not ip.is_alive(): proclist.remove(ip)            
                        time.sleep(0.01)
                 jframe1=jframe_split_list[iproc-1]
                 jframe2=jframe_split_list[iproc]
                 sp = Process(target=docol, name="docol proc", kwargs={"iproc":iproc-1,"pdist":pdist,"psim":psim,"iframe":iframe,"jframe1":jframe1,"jframe2":jframe2})  
                 proclist.append(sp)
                 sp.start()
                 sys.stderr.write("Landmark %d, Matrix row %d, %d active processes     \r" % (iland,jframe2, len(proclist)))
             
                 # waits for all threads to finish
              for ip in proclist:
                   while ip.is_alive(): ip.join(0.1)  
         
                # copies from the shared memory array to Sim.
              for jframe in range(nf):
                   dist_list[jframe]=pdist[jframe]
                   for iproc in range(1,nprocs):
                     if(dist_list[jframe]>pdist[iproc*nf+jframe]):
                       # print iproc,pdist[iproc*nf+jframe]
                        dist_list[jframe]=pdist[iproc*nf+jframe]
                   sim_rect[iland][jframe]=psim[jframe]    
            if(partialsim):
                for x in sim_rect[iland,:]:
                   pfkernel.write("%20.12e " % (x))
                pfkernel.write("\n")
              #========================================================================        
              
        if(partialsim):pfkernel.close()
        for iland in range(0,m):
            for jland in range(0,m):
                sim[iland,jland] = sim_rect[iland, landmarks[jland] ]
        
        fkernel = open(prefix+".landmarks.k", "w")  
        fkernel.write("# Kernel matrix for landmarks from  %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s " % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)) )
        if (usekit):fkernel.write( " Using reference kit: %s " % (str(kit)) )
        if (alchemyrules!="none"):fkernel.write( " Using alchemy rules: %s " % (alchemyrules) )
        if (kmode=="regmatch"): fkernel.write( " Regularized parameter: %f " % (reggamma) )
        fkernel.write("\n")
        for iframe in range(0,m):
            for x in sim[iframe][0:m]:
                fkernel.write("%20.12e " % (x))
            fkernel.write("\n")   
        fkernel.close()
        
        fkernel = open(prefix+".oos.k", "w")  
        fkernel.write("# Kernel matrix for OOS from %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s" % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)) )
        if (usekit):fkernel.write( " Using reference kit: %s " % (str(kit)) )
        if (alchemyrules!="none"):fkernel.write( " Using alchemy rules: %s " % (alchemyrules) )
        if (kmode=="regmatch"): fkernel.write( " Regularized parameter: %f " % (reggamma) )
        fkernel.write("\n")
        for jframe in range(0,nf):
            for x in sim_rect[:,jframe]:
                fkernel.write("%20.12e " % (x))
            fkernel.write("\n")   
        fkernel.close()            
            
        if printsim:
            fsim = open(prefix+".landmarks.sim", "w")  
            fsim.write("# Distance matrix for %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s" % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)))
            if (usekit):fsim.write( " Using reference kit: %s " % (str(kit)) )
            if (alchemyrules!="none"):fsim.write( " Using alchemy rules: %s " % (alchemyrules) )
            if (kmode=="regmatch"): fsim.write( " Regularized parameter: %f " % (reggamma) )
            fsim.write("\n")
            for iframe in range(0,m):
                for x in sim[iframe][0:m]:
                    fsim.write("%16.8e " % (np.sqrt(max(2-2*x,0))))
                fsim.write("\n")   
            fsim.close()
            
            fsim = open(prefix+".oos.sim", "w")  
            fsim.write("# OOS Distance matrix for %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s" % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)))
            if (usekit):fsim.write( " Using reference kit: %s " % (str(kit)) )
            if (alchemyrules!="none"):fsim.write( " Using alchemy rules: %s " % (alchemyrules) )
            if (kmode=="regmatch"): fsim.write( " Regularized parameter: %f " % (reggamma) )
            fsim.write("\n")
            for jframe in range(0,nf):
                for x in sim_rect[:,jframe]:
                    fsim.write("%16.8e " % (np.sqrt(max(2-2*x,0))))
                fsim.write("\n")   
            fsim.close()
            
    else:  # standard case (one input, compute everything
        sim=np.zeros((nf,nf))

        if (nprocs<=1):
            # no multiprocess
            for iframe in range (0, nf):
                sim[iframe,iframe]=1.0
                sli = sl[iframe]
                for jframe in range(0,iframe):
                    if verbose:
                        fij = open(prefix+".environ-"+str(iframe)+"-"+str(jframe)+".dat", "w")
                    else: fij = None
                    # if periodic: sys.stderr.write("comparing %3d, atoms cell with  %3d atoms cell: lcm: %3d \r" % (sl[iframe].nenv, sl[jframe].nenv, lcm(sl[iframe].nenv,sl[jframe].nenv))) 
                    sij = structk(sli, sl[jframe], alchem, periodic, mode=kmode, fout=fij, peps = permanenteps, gamma=reggamma)          
                    sim[iframe][jframe]=sim[jframe][iframe]=sij/np.sqrt(nrm[iframe]*nrm[jframe])
                sys.stderr.write("Matrix row %d                           \r" % (iframe))
        else:      
            # multiple processors
            def dorow(irow, nf, psim):
                sli=sl[irow] 
                for jframe in range(0,irow):
                    sij = structk(sli, sl[jframe], alchem, periodic, mode=kmode, peps = permanenteps, gamma=reggamma)          
                    psim[irow*nf+jframe]=sij/np.sqrt(nrm[irow]*nrm[jframe])  
               
            proclist = []   
            psim = Array('d', nf*nf, lock=False)      
            for iframe in range (0, nf):
                sim[iframe,iframe]=1.0
                while(len(proclist)>=nprocs):
                    for ip in proclist:
                        if not ip.is_alive(): proclist.remove(ip)            
                        time.sleep(0.01)
                sp = Process(target=dorow, name="doframe proc", kwargs={"irow":iframe, "nf":nf, "psim": psim})  
                proclist.append(sp)
                sp.start()
                sys.stderr.write("Matrix row %d, %d active processes     \r" % (iframe, len(proclist)))
            
            # waits for all threads to finish
            for ip in proclist:
                while ip.is_alive(): ip.join(0.1)  
         
            # copies from the shared memory array to Sim.
            for iframe in range (0, nf):      
                for jframe in range(0,iframe):
                    sim[iframe,jframe]=sim[jframe,iframe]=psim[iframe*nf+jframe]
     
        fkernel = open(prefix+".k", "w")  
        fkernel.write("# Kernel matrix for %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s " % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)) )
        if (usekit):fkernel.write( " Using reference kit: %s " % (str(kit)) )
        if (alchemyrules!="none"):fkernel.write( " Using alchemy rules: %s " % (alchemyrules) )
        if (kmode=="regmatch"): fkernel.write( " Regularized parameter: %f " % (reggamma) )
        fkernel.write("\n")
        for iframe in range(0,nf):
            for x in sim[iframe][0:nf]:
                fkernel.write("%16.8e " % (x))
            fkernel.write("\n")   
            
        if printsim:
            fsim = open(prefix+".sim", "w")  
            fsim.write("# Distance matrix for %s. Cutoff: %f  Nmax: %d  Lmax: %d  Atoms-sigma: %f  Mu: %f  Central-weight: %f  Periodic: %s  Kernel: %s  Ignored_Z: %s  Ignored_Centers_Z: %s " % (filename, coff, nd, ld, gs, mu, centerweight, periodic, kmode, str(noatom), str(nocenter)) )
            if (usekit):fsim.write( " Using reference kit: %s " % (str(kit)) )
            if (alchemyrules!="none"):fsim.write( " Using alchemy rules: %s " % (alchemyrules) )
            if (kmode=="regmatch"): fsim.write( " Regularized parameter: %f " % (reggamma) )
            fsim.write("\n")
            for iframe in range(0,nf):
                for x in sim[iframe][0:nf]:
                    fsim.write("%16.8e " % (np.sqrt(max(2-2*x,0))))
                fsim.write("\n")  
    sys.stderr.write("\n ============= Glosim Ended Successfully ============== \n") 
def gcd(a,b):
   if (b>a): a,b = b, a

   while (b):  a, b = b, a%b

   return a

def lcm(a,b):
   return a*b/gcd(b,a)

if __name__ == '__main__':
      parser = argparse.ArgumentParser(description="""Computes the similarity matrix between a set of atomic structures 
                           based on SOAP descriptors and an optimal assignment of local environments.""")
                           
      parser.add_argument("filename", nargs=1, help="Name of the LibAtom formatted xyz input file")
      parser.add_argument("--periodic", action="store_true", help="Matches structures with different atom numbers by replicating the environments")
      parser.add_argument("--exclude", type=str, default="", help="Comma-separated list of atom Z to be removed from the input structures (e.g. --exclude 96,101)")
      parser.add_argument("--nocenter", type=str, default="", help="Comma-separated list of atom Z to be ignored as environment centers (e.g. --nocenter 1,2,4)")
      parser.add_argument("--verbose",  action="store_true", help="Writes out diagnostics for the optimal match assignment of each pair of environments")   
      parser.add_argument("-n", type=int, default='8', help="Number of radial functions for the descriptor")
      parser.add_argument("-l", type=int, default='6', help="Maximum number of angular functions for the descriptor")
      parser.add_argument("-c", type=float, default='5.0', help="Radial cutoff")
      parser.add_argument("-g", type=float, default='0.5', help="Atom Gaussian sigma")
      parser.add_argument("-cw", type=float, default='1.0', help="Center atom weight")
      parser.add_argument("--mu", type=float, default='0.0', help="Extra penalty for comparing to missing atoms")
      parser.add_argument("--usekit", action="store_true", help="Computes the least commond denominator of all structures and uses that as a reference state")      
      parser.add_argument("--gamma", type=float, default="1.0", help="Regularization for entropy-smoothed best-match kernel")
      parser.add_argument("--kit", type=str, default="auto", help="Dictionary-style kit specification (e.g. --kit '{4:1,6:10}'")
      parser.add_argument("--alchemy_rules", type=str, default="none", help='Dictionary-style rule specification in quote (e.g. --alchemy_rules "{(6,7):1,(6,8):1}"')
      parser.add_argument("--kernel", type=str, default="match", help="Global kernel mode (e.g. --kernel average / match / regmatch")      
      parser.add_argument("--permanenteps", type=float, default="0.0", help="Tolerance level for approximate permanent (e.g. --permanenteps 1e-4")     
      parser.add_argument("--distance", action="store_true", help="Also prints out similarity (as kernel distance)")
      parser.add_argument("--np", type=int, default='1', help="Use multiple processes to compute the kernel matrix")
      parser.add_argument("--ij", type=str, default='', help="Compute and print diagnostics for the environment similarity between frames i,j (e.g. --ij 3,4)")
      parser.add_argument("--nlandmarks", type=int,default='0',help="Use farthest point sampling method to select n landmarks. This will also generate the OOS matrix for rest of the frames")     
      parser.add_argument("--refxyz", type=str, default='', help="ref xyz file if you want to compute the rectangular matrix contaning distances from ref configurations")
      parser.add_argument("--prefix", type=str, default='', help="Prefix for output files (defaults to input file name)")
      parser.add_argument("--livek",  action="store_true", help="Writes out diagnostics for the optimal match assignment of each pair of environments")   
      parser.add_argument("--lowmem",  action="store_true", help="Writes out diagnostics for the optimal match assignment of each pair of environments")   
      
           
      args = parser.parse_args()

      if args.exclude == "":
         noatom = []
      else: 
         noatom = map(int,args.exclude.split(','))
       
      if args.nocenter == "":
         nocenter = []
      else: 
         nocenter = map(int,args.nocenter.split(','))   
            
      nocenter = sorted(list(set(nocenter+noatom)))
       
      if (args.verbose and args.np>1): raise ValueError("Cannot write out diagnostics when running parallel jobs") 
          
      if args.ij == "":
         envij=None
      else:
         envij=tuple(map(int,args.ij.split(",")))
                  
      main(args.filename, nd=args.n, ld=args.l, coff=args.c, gs=args.g, mu=args.mu, centerweight=args.cw, periodic=args.periodic, usekit=args.usekit, kit=args.kit,alchemyrules=args.alchemy_rules, kmode=args.kernel, permanenteps=args.permanenteps, reggamma=args.gamma, noatom=noatom, nocenter=nocenter, nprocs=args.np, verbose=args.verbose, envij=envij, prefix=args.prefix, nlandmark=args.nlandmarks, printsim=args.distance,ref_xyz=args.refxyz,partialsim=args.livek,lowmem=args.lowmem)
