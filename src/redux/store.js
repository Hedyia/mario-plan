import { createStore } from "redux";
import { rootReducer } from "./root/root.reducer";

const store = createStore(rootReducer);

export default store;
