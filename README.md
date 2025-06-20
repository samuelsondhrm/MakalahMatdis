# MakalahMatdis

This Python program simulates a basic production scheduling algorithm for a manufacturing company, PT Yane Manufaktur Indonesia. It efficiently manages various types of production orders, assigns them to available machinery, and allocates necessary human resources (operators) while calculating estimated completion times and power consumption.

The simulator features a decision-tree-like workflow to handle different product types, distinguishing between Forming processes (for products like Yane600, Yane672, Yane750, SD680, Kabe325) and Shearing & Bending processes (for Accessories). It prioritizes urgent orders and attempts to find the best available machine unit and operator slots for each task within daily work hours. If an order cannot be scheduled on the current day due to resource constraints, it's automatically pushed to the next available working day.
