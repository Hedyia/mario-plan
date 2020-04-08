import { combineReducers } from "redux";
import { authReducer } from "../auth/auth.reducer";
import { projectReducer } from "../project/project.reducer";

export const rootReducer = combineReducers({
  auth: authReducer,
  project: projectReducer,
});
