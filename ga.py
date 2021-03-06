# This file uses genetic algorithm to optimaize the parameters of 
# matched filter response.

# In this script, we use DEAP to implement genetic algorithm. You 
# can install it follow the link: https://github.com/DEAP/deap.

# The input files are original image and its ground truth image and 
# the output is the optimaized parameters.

import random
import mfr
from deap import base
from deap import creator
from deap import tools
import numpy as np
import sys
import timeit
import cv2

# im0 is the original image and gt is its ground truth. 
# and then, we convert these images into grayscale images.
im0 = cv2.imread(sys.argv[1])
gt = cv2.imread(sys.argv[2])
im1 = cv2.cvtColor(im0, cv2.COLOR_BGR2GRAY)
gt = cv2.cvtColor(gt, cv2.COLOR_BGR2GRAY)

# in order to reduce the quantization error, we convert the 
# 8-bit image to float image. 
im1 = im1.astype(np.float32) / 255.0
gt = gt.astype(np.float32) / 255.0

# create two variables of individual and fitness function. 
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)

# create a base variable in DEAP
toolbox = base.Toolbox()

# func is used for randomly generate individual with different range 
# of parameters: 
# L: the length of the neighborhood along the y-axis to smooth noise (1-15)
# sigma: the standard deviation of Gaussian function
# w: the kernel size of the low-pass filter before compute MFR-FDoG
# c: the gain of threshold
func = [lambda:random.randint(1, 15), lambda:random.uniform(0.35, 10), \
        lambda:random.randint(3, 50), lambda:random.uniform(0.1, 5)]

# Structure initializers
# define 'individual' to be an individual
# consisting of 4 parameters generated by func.
toolbox.register("individual", tools.initCycle, creator.Individual, 
    func, 1)

# define the population to be a list of individuals
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

# define the number of individual 
numi = 0

# the goal ('fitness') function to be maximized
# the fitness function is Dice coefficient. 
def evalOneMax(individual):
    global numi
    # compute runing time of each individual
    evalstart = timeit.default_timer()

    # define a varialbe of matched filter response.
    matched = mfr.MFR(individual[0], individual[1], individual[2], individual[3])

    # generate Gaussian and first-order derivative of Gaussian filers and their 
    # filter bank.
    gf = matched.gaussian_matched_filter_kernel()
    fdog = matched.fdog_filter_kernel()
    bank_gf = matched.createMatchedFilterBank(gf, 12)
    bank_fdog = matched.createMatchedFilterBank(fdog, 12)

    # generate matched filter response of both filters.
    H = matched.applyFilters(im1, bank_gf)
    D = matched.applyFilters(im1, bank_fdog)

    # compute the threshold value using MFR-FDoG
    kernel = np.ones((matched.w,matched.w),np.float32)/(matched.w*matched.w)
    dm = np.zeros(D.shape,np.float32)
    DD = np.array(D, dtype='f')
    dm = cv2.filter2D(DD,-1,kernel)
    dmn = cv2.normalize(dm, dm, 0, 1, cv2.NORM_MINMAX)
    uH = cv2.mean(H)
    Tc = matched.c * uH[0]
    T = (1+dmn) * Tc 

    # compute Dice coefficient.
    a, b, i = 0., 0., 0.
    (h, w) = H.shape
    for y in range(h):
        for x in range(w):
            if H[y][x] >= T[y][x] and gt[y][x]:
                i += 1
                a += 1
                b += 1
            elif H[y][x] >= T[y][x] and not gt[y][x]:
                a += 1
            elif H[y][x] < T[y][x] and gt[y][x]:
                b += 1
            elif H[y][x] < T[y][x] and not gt[y][x]:
                pass
    dice = 2*i/(a+b)

    # compute runing time of each individual
    evalstop = timeit.default_timer()
    numi += 1
    print "individual: ", numi, ": ", individual, "  dice: ", round(dice, 2), \
          "time consuming: ", round(evalstop - evalstart, 2)
    return dice,

#----------
# Operator registration
#----------
# register the goal / fitness function
toolbox.register("evaluate", evalOneMax)

# register the crossover operator
toolbox.register("mate", tools.cxTwoPoint)

# register a mutation operator with a probability to
# flip each attribute/gene of 0.05
toolbox.register("mutate", tools.mutFlipBit, indpb=0.05)

# operator for selecting individuals for breeding the next
# generation: each individual of the current generation
# is replaced by the 'fittest' (best) of three individuals
# drawn randomly from the current generation.
toolbox.register("select", tools.selTournament, tournsize=3)

#----------

def main():
    global numi
    start = timeit.default_timer()
    random.seed(64)

    # create an initial population of 300 individuals (where
    # each individual is a list of integers)
    pop = toolbox.population(n=50)

    # CXPB  is the probability with which two individuals
    #       are crossed
    #
    # MUTPB is the probability for mutating an individual
    #
    # NGEN  is the number of generations for which the
    #       evolution runs
    CXPB, MUTPB, NGEN = 0.5, 0.2, 30
    
    print("Start of evolution")
    
    # Evaluate the entire population
    fitnesses = list(map(toolbox.evaluate, pop))
    for ind, fit in zip(pop, fitnesses):
        ind.fitness.values = fit
    
    print("  Evaluated %i individuals" % len(pop))
    
    # Begin the evolution
    for g in range(NGEN):
        print("-- Generation %i --" % g)
        loopstart = timeit.default_timer()
        # Select the next generation individuals
        offspring = toolbox.select(pop, len(pop))
        # Clone the selected individuals
        offspring = list(map(toolbox.clone, offspring))
        
        # Apply crossover and mutation on the offspring
        for child1, child2 in zip(offspring[::2], offspring[1::2]):

            # cross two individuals with probability CXPB
            if random.random() < CXPB:
                toolbox.mate(child1, child2)

                # fitness values of the children
                # must be recalculated later
                del child1.fitness.values
                del child2.fitness.values

        for mutant in offspring:

            # mutate an individual with probability MUTPB
            if random.random() < MUTPB:
                toolbox.mutate(mutant)
                del mutant.fitness.values
    
        # Evaluate the individuals with an invalid fitness
        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalid_ind)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit
        
        print("  Evaluated %i individuals" % len(invalid_ind))
        
        # The population is entirely replaced by the offspring
        pop[:] = offspring
        
        # Gather all the fitnesses in one list and print the stats
        fits = [ind.fitness.values[0] for ind in pop]
        
        length = len(pop)
        mean = sum(fits) / length
        sum2 = sum(x*x for x in fits)
        std = abs(sum2 / length - mean**2)**0.5
        
        print("  Min %s" % min(fits))
        print("  Max %s" % max(fits))
        print("  Avg %s" % mean)
        print("  Std %s" % std)
        numi = 0
        loopstop = timeit.default_timer()
        print "  loop time consuming: ", round(loopstop - loopstart, 2)

    print("-- End of (successful) evolution --")
    
    best_ind = tools.selBest(pop, 1)[0]
    print("Best individual is %s, %s" % (best_ind, best_ind.fitness.values))
    stop = timeit.default_timer()
    print "time consuming: ", stop - start 
if __name__ == "__main__":
    main()