import React from "react";
import { NavLink } from "react-router-dom";

const SignIn = () => {
  return (
    <ul className="right">
      <li>
        <NavLink to="/new-project">New Project</NavLink>
      </li>
      <li>
        <NavLink to="/sign-in">Log Out</NavLink>
      </li>
      <li>
        <NavLink to="/" className="btn btn-floating pink lighten-1">
          MH
        </NavLink>
      </li>
    </ul>
  );
};

export default SignIn;
