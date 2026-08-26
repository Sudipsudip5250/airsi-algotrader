import { Router, type IRouter } from "express";
import healthRouter from "./health";
import botRouter from "./bot";
import experimentsRouter from "./experiments";

const router: IRouter = Router();

router.use(healthRouter);
router.use(botRouter);
router.use(experimentsRouter);

export default router;
