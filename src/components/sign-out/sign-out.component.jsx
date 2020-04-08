import React from "react";
import { NavLink } from "react-router-dom";

const SignOut = () => {
  return (
    <ul className="right">
      <li>
        <NavLink to="/auth">Sign Up</NavLink>
      </li>
      <li>
        <NavLink to="/auth">Sign In</NavLink>
      </li>
    </ul>
  );
};

export default SignOut;
